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

// Run makes one fresh TLS connection and transfers exactly one resource.
func Run(parent context.Context, addr string, cfg *tls.Config, expected *workload.Store, timeout time.Duration) (out transport.Result, err error) {
	if cfg == nil || expected == nil || expected.Count() != 1 || timeout <= 0 {
		return out, fmt.Errorf("invalid P2 client configuration")
	}
	r, _ := expected.Resource(1)
	recv, err := protocol.NewReceiver(1, uint64(r.Size()), r.SHA256(), uint32(expected.Profile().ChunkBytes))
	if err != nil {
		return out, err
	}
	out.ResourceID, out.BytesExpected = 1, uint64(r.Size())
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()
	out.Timing.Start = time.Now()
	defer func() { out.Timing.End = time.Now(); out.BytesReceived = recv.BytesReceived() }()
	raw, err := (&net.Dialer{}).DialContext(ctx, "tcp", addr)
	if err != nil {
		return out, err
	}
	out.Timing.TCPConnected = time.Now()
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
	_ = conn.SetDeadline(time.Now().Add(timeout))
	if err := conn.HandshakeContext(ctx); err != nil {
		return out, err
	}
	out.Timing.Handshake = time.Now()
	if conn.ConnectionState().NegotiatedProtocol != "quicbench/1" {
		return out, fmt.Errorf("unexpected ALPN")
	}
	request, err := protocol.RequestFrame(1, 1, uint32(expected.Profile().ChunkBytes))
	if err != nil {
		return out, err
	}
	out.Timing.RequestStart = time.Now()
	if err := protocol.WriteFrame(conn, request, uint32(expected.Profile().ChunkBytes)); err != nil {
		return out, err
	}
	out.Timing.RequestEnd = time.Now()
	for !recv.Complete() {
		f, readErr := protocol.ReadFrameObserved(conn, uint32(expected.Profile().ChunkBytes), func() {
			if out.Timing.FirstByte.IsZero() {
				out.Timing.FirstByte = time.Now()
			}
		})
		if readErr != nil {
			return out, readErr
		}
		if err := recv.Accept(f); err != nil {
			return out, err
		}
		if recv.BytesReceived() == uint64(r.Size()) && out.Timing.PayloadDone.IsZero() {
			out.Timing.PayloadDone = time.Now()
		}
	}
	out.Timing.Done = time.Now()
	// The server closes after FIN. Reject a duplicate FIN or any trailing frame.
	var extra [1]byte
	n, readErr := conn.Read(extra[:])
	if n != 0 || !errors.Is(readErr, io.EOF) {
		return out, fmt.Errorf("trailing response or missing EOF: n=%d err=%v", n, readErr)
	}
	if err := recv.Verify(); err != nil {
		return out, err
	}
	out.ChecksumOK = true
	return out, nil
}
