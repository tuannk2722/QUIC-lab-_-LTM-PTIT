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

// RunBatch uses one fresh QUIC connection and one bidirectional stream for
// each resource. Requests are written independently after all streams open.
func RunBatch(parent context.Context, addr string, cfg *tls.Config, expected *workload.Store, timeout time.Duration) (out []transport.Result, err error) {
	if cfg == nil || expected == nil || expected.Count() < 1 || expected.Count() > maxBidiStreams || timeout <= 0 {
		return nil, fmt.Errorf("invalid QUIC client configuration")
	}
	count, chunk := expected.Count(), uint32(expected.Profile().ChunkBytes)
	receivers := make([]*protocol.Receiver, count)
	out = make([]transport.Result, count)
	for i := range out {
		resource, resourceErr := expected.Resource(uint32(i + 1))
		if resourceErr != nil {
			return nil, resourceErr
		}
		receivers[i], err = protocol.NewReceiver(resource.ID(), uint64(resource.Size()), resource.SHA256(), chunk)
		if err != nil {
			return nil, err
		}
		out[i].ResourceID, out[i].BytesExpected = resource.ID(), uint64(resource.Size())
	}
	handshakeTimeout := min(timeout, 10*time.Second)
	qcfg := quicConfig(handshakeTimeout, timeout)
	// The peer may only respond on streams that this client opened.
	qcfg.MaxIncomingStreams = -1
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()
	start := time.Now() // Includes address resolution and socket setup, as TCP Dial does.
	for i := range out {
		out[i].Timing.Start = start
	}
	defer func() {
		end := time.Now()
		for i := range out {
			out[i].Timing.End = end
			out[i].BytesReceived = receivers[i].BytesReceived()
		}
	}()
	peer, err := resolveUDP(ctx, addr, net.DefaultResolver.LookupIPAddr)
	if err != nil {
		return out, err
	}
	packet, err := net.ListenPacket("udp", ":0")
	if err != nil {
		return out, err
	}
	defer packet.Close()
	dialCtx, stopDial := context.WithTimeout(ctx, handshakeTimeout)
	conn, err := quicgo.Dial(dialCtx, packet, peer, cfg, qcfg)
	stopDial()
	if err != nil {
		return out, err
	}
	defer conn.CloseWithError(0, "trial complete")
	stop := make(chan struct{})
	go func() {
		select {
		case <-ctx.Done():
			_ = conn.CloseWithError(appProtocolError, "trial cancelled")
		case <-stop:
		}
	}()
	defer close(stop)
	if conn.ConnectionState().TLS.NegotiatedProtocol != tlsconfig.ALPN || conn.ConnectionState().Version != quicgo.Version1 {
		return out, fmt.Errorf("unexpected QUIC ALPN/version")
	}
	handshake := time.Now() // Dial returns after the secure handshake in cold mode.
	for i := range out {
		out[i].Timing.Handshake = handshake
	}
	streams := make([]*quicgo.Stream, count)
	deadline, _ := ctx.Deadline()
	for i := range streams {
		stream, openErr := conn.OpenStreamSync(ctx)
		if openErr != nil {
			return out, openErr
		}
		_ = stream.SetDeadline(deadline)
		id := int64(stream.StreamID())
		out[i].StreamID = &id
		streams[i] = stream
	}
	var wg sync.WaitGroup
	errCh := make(chan error, count)
	for i, stream := range streams {
		i, stream := i, stream
		wg.Go(func() {
			if workerErr := receiveResource(stream, uint32(i+1), uint32(count), chunk, receivers[i], &out[i]); workerErr != nil {
				if ctx.Err() != nil {
					workerErr = errors.Join(workerErr, ctx.Err())
				}
				out[i].Err = workerErr
				errCh <- fmt.Errorf("resource %d stream %d: %w", i+1, stream.StreamID(), workerErr)
				cancel()
				_ = conn.CloseWithError(appProtocolError, "resource failed")
			}
		})
	}
	wg.Wait()
	select {
	case err = <-errCh:
	default:
	}
	for i := range out {
		if receivers[i].Complete() {
			out[i].ChecksumChecked = true
			verifyErr := receivers[i].Verify()
			out[i].ChecksumOK = verifyErr == nil
			if verifyErr != nil {
				out[i].Err = verifyErr
				if err == nil {
					err = fmt.Errorf("resource %d: %w", i+1, verifyErr)
				}
			}
		}
	}
	return out, err
}

func receiveResource(stream *quicgo.Stream, id, count, chunk uint32, receiver *protocol.Receiver, result *transport.Result) error {
	complete := false
	defer func() {
		if !complete {
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
