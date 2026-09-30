package tcp

import (
	"context"
	"crypto/tls"
	"fmt"
	"net"
	"sync"
	"time"

	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/workload"
)

type ServerOptions struct {
	HandshakeTimeout time.Duration
	TrialTimeout     time.Duration
	MaxConnections   int
}

// Serve handles the P2 single-resource TCP/TLS profile. Batch scheduling is P3.
func Serve(ctx context.Context, addr string, cfg *tls.Config, store *workload.Store, opts ServerOptions, ready chan<- net.Addr) error {
	if cfg == nil || store == nil || store.Count() != 1 || opts.HandshakeTimeout <= 0 || opts.TrialTimeout <= 0 || opts.MaxConnections < 1 || opts.MaxConnections > 8 {
		return fmt.Errorf("invalid P2 server configuration")
	}
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}
	defer ln.Close()
	stopped := make(chan struct{})
	go func() {
		select {
		case <-ctx.Done():
			ln.Close()
		case <-stopped:
		}
	}()
	defer close(stopped)
	if ready != nil {
		select {
		case ready <- ln.Addr():
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	sem := make(chan struct{}, opts.MaxConnections)
	var wg sync.WaitGroup
	defer wg.Wait()
	for {
		conn, err := ln.Accept()
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			return err
		}
		select {
		case sem <- struct{}{}:
			wg.Go(func() { defer func() { <-sem }(); serveConn(ctx, conn, cfg, store, opts) })
		default:
			conn.Close()
		}
	}
}

func serveConn(ctx context.Context, raw net.Conn, cfg *tls.Config, store *workload.Store, opts ServerOptions) {
	conn := tls.Server(raw, cfg)
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
	_ = conn.SetDeadline(time.Now().Add(opts.HandshakeTimeout))
	if err := conn.HandshakeContext(ctx); err != nil {
		return
	}
	if conn.ConnectionState().NegotiatedProtocol != "quicbench/1" {
		return
	}
	_ = conn.SetDeadline(time.Now().Add(opts.TrialTimeout))
	f, err := protocol.ReadFrame(conn, 65536)
	if err != nil {
		return
	}
	count, chunk, err := protocol.ParseRequest(f)
	if err != nil || count != 1 || f.ResourceID != 1 || int64(chunk) != store.Profile().ChunkBytes {
		e, _ := protocol.ErrorFrame(1, protocol.CodeInvalidBatch, "expected one configured resource")
		_ = protocol.WriteFrame(conn, e, 65536)
		return
	}
	r, _ := store.Resource(1)
	if err := protocol.WriteFrame(conn, protocol.MetaFrame(1, uint64(r.Size()), r.SHA256()), chunk); err != nil {
		return
	}
	buf := make([]byte, int(chunk))
	for off := int64(0); off < r.Size(); {
		want := min(int64(len(buf)), r.Size()-off)
		n, readErr := r.ReadAt(buf[:want], off)
		if readErr != nil || n != int(want) {
			return
		}
		if err := protocol.WriteFrame(conn, protocol.Frame{Type: protocol.Data, ResourceID: 1, Offset: uint64(off), Payload: buf[:n]}, chunk); err != nil {
			return
		}
		off += int64(n)
	}
	_ = protocol.WriteFrame(conn, protocol.Frame{Type: protocol.Fin, ResourceID: 1, Offset: uint64(r.Size())}, chunk)
}
