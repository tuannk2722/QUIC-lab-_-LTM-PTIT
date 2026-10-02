package quic

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"net"
	"strconv"
	"sync"
	"time"

	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/tlsconfig"
	"quic-performance-lab/internal/transport"
	"quic-performance-lab/internal/workload"

	quicgo "github.com/quic-go/quic-go"
)

// RunBatch always uses an empty cache, including when the caller supplies one.
func RunBatch(parent context.Context, addr string, cfg *tls.Config, expected *workload.Store, timeout time.Duration) ([]transport.Result, error) {
	if cfg == nil {
		return nil, fmt.Errorf("nil TLS config")
	}
	cold := cfg.Clone()
	cold.ClientSessionCache = nil
	out, _, err := runBatch(parent, addr, cold, expected, timeout, false, nil, 0)
	return out, err
}

func prepare(expected *workload.Store, start time.Time) ([]transport.Result, []*protocol.Receiver, error) {
	out := make([]transport.Result, expected.Count())
	receivers := make([]*protocol.Receiver, len(out))
	for i := range out {
		resource, err := expected.Resource(uint32(i + 1))
		if err != nil {
			return nil, nil, err
		}
		receivers[i], err = protocol.NewReceiver(resource.ID(), uint64(resource.Size()), resource.SHA256(), uint32(expected.Profile().ChunkBytes))
		if err != nil {
			return nil, nil, err
		}
		out[i] = transport.Result{ResourceID: resource.ID(), BytesExpected: uint64(resource.Size()), Timing: transport.Timing{Start: start}}
	}
	return out, receivers, nil
}

// runBatch prepares before t0, then owns one connection and at most two batch
// attempts. Only the coordinator calls NextConnection and replays a batch.
func runBatch(parent context.Context, addr string, cfg *tls.Config, expected *workload.Store, timeout time.Duration, early bool, ticket *tlsconfig.TicketCache, ticketTimeout time.Duration) (out []transport.Result, attempts []transport.Attempt, err error) {
	if cfg == nil || expected == nil || expected.Count() < 1 || expected.Count() > maxBidiStreams || timeout <= 0 {
		return nil, nil, fmt.Errorf("invalid QUIC client configuration")
	}
	out, receivers, err := prepare(expected, time.Time{})
	if err != nil {
		return nil, nil, err
	}
	handshakeTimeout := min(timeout, 10*time.Second)
	qcfg := quicConfig(handshakeTimeout, timeout)
	qcfg.MaxIncomingStreams = -1
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()
	start := time.Now()
	for i := range out {
		out[i].Timing.Start = start
	}
	session := &transport.SessionState{}
	defer func() {
		end := time.Now()
		for i := range out {
			out[i].Timing.End = end
			out[i].BytesReceived = receivers[i].BytesReceived()
			out[i].Session = session
		}
		attempts = append(attempts, transport.Attempt{Index: out[0].AttemptIndex, Results: append([]transport.Result(nil), out...), Err: err})
	}()
	peer, err := resolveUDP(ctx, addr, net.DefaultResolver.LookupIPAddr)
	if err != nil {
		return out, attempts, err
	}
	packet, err := net.ListenPacket("udp", ":0")
	if err != nil {
		return out, attempts, err
	}
	defer packet.Close()
	dialCtx, stopDial := context.WithTimeout(ctx, handshakeTimeout)
	defer stopDial()
	var conn *quicgo.Conn
	if early {
		session.Attempted0RTT = true
		conn, err = quicgo.DialEarly(dialCtx, packet, peer, cfg, qcfg)
	} else {
		conn, err = quicgo.Dial(dialCtx, packet, peer, cfg, qcfg)
	}
	if err != nil {
		return out, attempts, err
	}
	defer conn.CloseWithError(0, "trial complete")
	var earlyReady time.Time
	if early {
		earlyReady = time.Now()
	}
	type handshakeEvent struct {
		at  time.Time
		err error
	}
	observed := make(chan handshakeEvent, 1)
	// Begin observing as soon as DialEarly exposes the connection. Join before
	// reading the event or state; never backdate an observed handshake.
	if early {
		go func() {
			select {
			case <-conn.HandshakeComplete():
				observed <- handshakeEvent{at: time.Now()}
			case <-conn.Context().Done():
				observed <- handshakeEvent{err: context.Cause(conn.Context())}
			case <-dialCtx.Done():
				observed <- handshakeEvent{err: dialCtx.Err()}
				_ = conn.CloseWithError(appProtocolError, "handshake deadline")
			}
		}()
	} else {
		observed <- handshakeEvent{at: time.Now()}
	}
	stop := make(chan struct{})
	stopped := make(chan struct{})
	go func() {
		defer close(stopped)
		select {
		case <-ctx.Done():
			_ = conn.CloseWithError(appProtocolError, "trial cancelled")
		case <-stop:
		}
	}()
	defer func() { close(stop); <-stopped }()
	var hs handshakeEvent
	if !early {
		hs = <-observed
	}
	err = runAttempt(ctx, conn, expected, receivers, out, start, earlyReady, hs.at, 0)
	if early {
		hs = <-observed
	}
	if hs.err != nil {
		err = errors.Join(err, hs.err)
	}
	state := conn.ConnectionState()
	if hs.err == nil && (state.TLS.NegotiatedProtocol != tlsconfig.ALPN || state.Version != quicgo.Version1) {
		err = errors.Join(err, fmt.Errorf("unexpected QUIC ALPN/version"))
	}
	var info *transport.ConnectionInfo
	if early && errors.Is(err, quicgo.Err0RTTRejected) {
		rejected := true
		session.EarlyRejected = &rejected
	}
	if !hs.at.IsZero() {
		info = transport.ObserveConnection(state.TLS, packet)
		info.QUICVersion = state.Version.String()
		used := state.Used0RTT
		info.Used0RTT = &used
		rejected := early && errors.Is(err, quicgo.Err0RTTRejected)
		session.EarlyRejected = &rejected
	}
	annotate := func(rows []transport.Result, end time.Time) {
		snapshot := *session
		for i := range rows {
			rows[i].Timing.Handshake = hs.at
			rows[i].Timing.End = end
			rows[i].Connection = info
			rows[i].Session = &snapshot
		}
	}
	if early && errors.Is(err, quicgo.Err0RTTRejected) {
		// All old workers have stopped. Preserve the failed attempt before
		// opening reset streams. The original t0 and connection survive.
		annotate(out, time.Now())
		for i := range out {
			out[i].BytesReceived = receivers[i].BytesReceived()
		}
		if hs.err != nil {
			return out, attempts, err
		}
		_, nextErr := conn.NextConnection(ctx)
		if nextErr != nil {
			return out, attempts, errors.Join(err, nextErr)
		}
		attempts = append(attempts, transport.Attempt{Index: 0, Results: append([]transport.Result(nil), out...), Err: err})
		session.FallbackCount = 1
		out, receivers, err = prepare(expected, start)
		if err != nil {
			return out, attempts, err
		}
		err = runAttempt(ctx, conn, expected, receivers, out, start, earlyReady, hs.at, 1)
	}
	annotate(out, time.Now())
	// No checksum work runs until all readers stop (both on success/failure).
	for i := range out {
		if receivers[i].Complete() {
			out[i].ChecksumChecked = true
			verifyErr := receivers[i].Verify()
			out[i].ChecksumOK = verifyErr == nil
			if verifyErr != nil {
				out[i].Err = verifyErr
				err = errors.Join(err, verifyErr)
			}
		}
	}
	if err == nil && ticket != nil {
		ticketCtx, stopTicket := context.WithTimeout(ctx, ticketTimeout)
		waitErr := ticket.Wait(ticketCtx)
		stopTicket()
		if waitErr != nil {
			err = fmt.Errorf("ticket delivery: %w", waitErr)
		}
	}
	return out, attempts, err
}

func runAttempt(ctx context.Context, conn *quicgo.Conn, expected *workload.Store, receivers []*protocol.Receiver, out []transport.Result, start, earlyReady, handshake time.Time, index int) (err error) {
	streams := make([]*quicgo.Stream, len(out))
	deadline, _ := ctx.Deadline()
	for i := range out {
		out[i].AttemptIndex = index
		out[i].Timing.Start = start
		out[i].Timing.EarlyReady = earlyReady
		out[i].Timing.Handshake = handshake
	}
	defer func() {
		// quic-go already invalidates rejected streams. Cancelling them can
		// enqueue control frames against IDs reused by the reset stream map.
		if errors.Is(err, quicgo.Err0RTTRejected) {
			return
		}
		for i, s := range streams {
			if s != nil && out[i].Timing.Done.IsZero() {
				s.CancelRead(streamProtocolError)
				s.CancelWrite(streamProtocolError)
			}
		}
	}()
	for i := range streams {
		stream, err := conn.OpenStreamSync(ctx)
		if err != nil {
			return err
		}
		_ = stream.SetDeadline(deadline)
		id := int64(stream.StreamID())
		out[i].StreamID = &id
		streams[i] = stream
	}
	var wg sync.WaitGroup
	errCh := make(chan error, len(out))
	for i, stream := range streams {
		wg.Go(func() {
			workerErr := receiveResource(stream, uint32(i+1), uint32(len(out)), uint32(expected.Profile().ChunkBytes), receivers[i], &out[i])
			if workerErr != nil {
				if ctx.Err() != nil {
					workerErr = errors.Join(workerErr, ctx.Err())
				}
				out[i].Err = workerErr
				errCh <- fmt.Errorf("resource %d stream %d: %w", i+1, stream.StreamID(), workerErr)
				// Rejected streams are invalidated by quic-go. Keep the
				// connection alive for the single coordinator's transition.
				if !errors.Is(workerErr, quicgo.Err0RTTRejected) {
					_ = conn.CloseWithError(appProtocolError, "resource failed")
				}
			}
		})
	}
	wg.Wait()
	close(errCh)
	for e := range errCh {
		err = errors.Join(err, e)
	}
	return err
}

func receiveResource(stream *quicgo.Stream, id, count, chunk uint32, receiver *protocol.Receiver, result *transport.Result) (err error) {
	complete := false
	defer func() {
		if !complete && !errors.Is(err, quicgo.Err0RTTRejected) {
			stream.CancelRead(streamProtocolError)
			stream.CancelWrite(streamProtocolError)
		}
	}()
	request, err := protocol.RequestFrame(id, count, chunk)
	if err != nil {
		return err
	}
	result.Timing.RequestStart = time.Now()
	if err := protocol.WriteFrame(stream, request, chunk); err != nil {
		return err
	}
	result.Timing.RequestEnd = time.Now()
	if err := stream.Close(); err != nil { // close only the client send-half
		return err
	}
	for !receiver.Complete() {
		frame, readErr := protocol.ReadFrameObserved(stream, chunk, func() {
			if result.Timing.FirstByte.IsZero() {
				result.Timing.FirstByte = time.Now()
			}
		})
		if readErr != nil {
			return fmt.Errorf("response before FIN: %w", readErr)
		}
		if err := receiver.Accept(frame); err != nil {
			return err
		}
		if receiver.BytesReceived() == result.BytesExpected && result.Timing.PayloadDone.IsZero() {
			result.Timing.PayloadDone = time.Now()
		}
		if receiver.Complete() {
			result.Timing.Done = time.Now()
		}
	}
	if err := expectStreamEOF(stream); err != nil {
		return err
	}
	complete = true
	return nil
}

func resolveUDP(ctx context.Context, addr string, lookup func(context.Context, string) ([]net.IPAddr, error)) (*net.UDPAddr, error) {
	host, port, err := net.SplitHostPort(addr)
	if err != nil {
		return nil, err
	}
	n, err := strconv.Atoi(port)
	if err != nil || n < 1 || n > 65535 {
		return nil, fmt.Errorf("invalid UDP port %q", port)
	}
	ips, err := lookup(ctx, host)
	if err != nil {
		return nil, err
	}
	if len(ips) == 0 {
		return nil, fmt.Errorf("no addresses for %q", host)
	}
	return &net.UDPAddr{IP: ips[0].IP, Zone: ips[0].Zone, Port: n}, nil
}
