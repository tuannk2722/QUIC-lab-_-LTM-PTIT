package tcp

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	"net"
	"time"

	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/transport"
	"quic-performance-lab/internal/workload"
)

// Run retains the one-resource API for callers of the P2 transfer.
func Run(parent context.Context, addr string, cfg *tls.Config, expected *workload.Store, timeout time.Duration) (transport.Result, error) {
	if expected == nil || expected.Count() != 1 {
		return transport.Result{}, fmt.Errorf("Run requires one resource")
	}
	results, err := RunBatch(parent, addr, cfg, expected, timeout)
	if len(results) == 0 {
		return transport.Result{}, err
	}
	return results[0], err
}

// RunBatch transfers all resources over one fresh TLS connection. Only the
// decoder reads from the connection; hashes run after every FIN has arrived.
func RunBatch(parent context.Context, addr string, cfg *tls.Config, expected *workload.Store, timeout time.Duration) (out []transport.Result, err error) {
	if cfg == nil || expected == nil || expected.Count() < 1 || expected.Count() > 64 || timeout <= 0 {
		return nil, fmt.Errorf("invalid TCP client configuration")
	}
	count := expected.Count()
	chunk := uint32(expected.Profile().ChunkBytes)
	receivers := make([]*protocol.Receiver, count)
	out = make([]transport.Result, count)
	for i := range out {
		r, resourceErr := expected.Resource(uint32(i + 1))
		if resourceErr != nil {
			return nil, resourceErr
		}
		receivers[i], err = protocol.NewReceiver(r.ID(), uint64(r.Size()), r.SHA256(), chunk)
		if err != nil {
			return nil, err
		}
		out[i].ResourceID, out[i].BytesExpected = r.ID(), uint64(r.Size())
		transport.PrepareProgress(&out[i], transport.ProgressEnabled(parent))
	}
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()
	start := time.Now()
	for i := range out {
		out[i].Timing.Start = start
	}
	defer func() {
		for i := range out {
			if !receivers[i].Complete() {
				continue
			}
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
		end := time.Now()
		for i := range out {
			out[i].Timing.End = end
			out[i].BytesReceived = receivers[i].BytesReceived()
		}
	}()
	raw, err := (&net.Dialer{}).DialContext(ctx, "tcp", addr)
	if err != nil {
		return out, err
	}
	tcpConnected := time.Now()
	for i := range out {
		out[i].Timing.TCPConnected = tcpConnected
	}
	conn := tls.Client(raw, cfg)
	defer conn.Close()
	stop := make(chan struct{})
	go func() {
		select {
		case <-ctx.Done():
			conn.Close()
		case <-stop:
		}
	}()
	defer close(stop)
	deadline, _ := ctx.Deadline()
	_ = conn.SetDeadline(deadline)
	if err := conn.HandshakeContext(ctx); err != nil {
		return out, err
	}
	handshake := time.Now()
	if conn.ConnectionState().NegotiatedProtocol != "quicbench/1" {
		return out, fmt.Errorf("unexpected ALPN")
	}
	defer func() {
		info := transport.ObserveConnection(conn.ConnectionState(), raw)
		for i := range out {
			out[i].Connection = info
		}
	}()
	for i := range out {
		out[i].Timing.Handshake = handshake
	}
	for i := range out {
		id := uint32(i + 1)
		request, requestErr := protocol.RequestFrame(id, uint32(count), chunk)
		if requestErr != nil {
			return out, requestErr
		}
		out[i].Timing.RequestStart = time.Now()
		if err := protocol.WriteFrame(conn, request, chunk); err != nil {
			return out, err
		}
		out[i].Timing.RequestEnd = time.Now()
	}
	if err := conn.CloseWrite(); err != nil {
		return out, err
	}
	remaining := count
	for remaining > 0 {
		f, readErr := protocol.ReadFrameObservedID(conn, chunk, func(id uint32) {
			if id >= 1 && int(id) <= count && out[id-1].Timing.FirstByte.IsZero() {
				out[id-1].Timing.FirstByte = time.Now()
			}
		})
		if readErr != nil {
			return out, readErr
		}
		if f.ResourceID < 1 || int(f.ResourceID) > count {
			return out, fmt.Errorf("response resource ID %d outside batch", f.ResourceID)
		}
		i := f.ResourceID - 1
		if err := receivers[i].Accept(f); err != nil {
			out[i].Err = err
			return out, err
		}
		if f.Type == protocol.Data {
			transport.RecordProgress(&out[i], receivers[i].BytesReceived())
		}
		if receivers[i].BytesReceived() == out[i].BytesExpected && out[i].Timing.PayloadDone.IsZero() {
			out[i].Timing.PayloadDone = time.Now()
		}
		if receivers[i].Complete() {
			out[i].Timing.Done = time.Now()
			remaining--
		}
	}
	var extra [1]byte
	n, readErr := conn.Read(extra[:])
	if n != 0 || !errors.Is(readErr, io.EOF) {
		cleanupErr := fmt.Errorf("trailing response or missing EOF: n=%d", n)
		if readErr != nil && !errors.Is(readErr, io.EOF) {
			if ctx.Err() != nil {
				readErr = errors.Join(readErr, ctx.Err())
			}
			cleanupErr = fmt.Errorf("response EOF: %w", readErr)
		}
		for i := range out {
			out[i].Err = cleanupErr
		}
		return out, cleanupErr
	}

	return out, err
}
