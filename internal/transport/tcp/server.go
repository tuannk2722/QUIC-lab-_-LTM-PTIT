package tcp

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	"net"
	"sync"
	"time"

	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/workload"
)

type ServerOptions struct {
	HandshakeTimeout time.Duration
	BatchTimeout     time.Duration
	TrialTimeout     time.Duration
	MaxConnections   int
	OnAccepted       func() // optional integration instrumentation
}

// Serve handles one request batch on each accepted TCP/TLS connection.
func Serve(ctx context.Context, addr string, cfg *tls.Config, store *workload.Store, opts ServerOptions, ready chan<- net.Addr) error {
	if cfg == nil || store == nil || store.Count() < 1 || store.Count() > 64 || opts.HandshakeTimeout <= 0 || opts.TrialTimeout <= 0 || opts.BatchTimeout < 0 || opts.MaxConnections < 1 || opts.MaxConnections > 8 {
		return fmt.Errorf("invalid TCP server configuration")
	}
	if opts.BatchTimeout == 0 {
		opts.BatchTimeout = 5 * time.Second
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
		if opts.OnAccepted != nil {
			opts.OnAccepted()
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
	trialEnd := time.Now().Add(opts.TrialTimeout)
	_ = conn.SetDeadline(trialEnd)
	batch, err := protocol.NewBatch(uint32(store.Count()), uint32(store.Profile().ChunkBytes))
	if err != nil {
		return
	}
	firstRequest := true
	for !batch.Complete() {
		f, readErr := protocol.ReadFrame(conn, 65536)
		if readErr != nil {
			if timeoutErr, ok := readErr.(net.Error); ok && timeoutErr.Timeout() && !firstRequest {
				e, _ := protocol.ErrorFrame(1, protocol.CodeBatchTimeout, "request batch timeout")
				_ = protocol.WriteFrame(conn, e, 65536)
			}
			return
		}
		if err := batch.Register(f); err != nil {
			e, _ := protocol.ErrorFrame(f.ResourceID, protocol.CodeInvalidBatch, "invalid request batch")
			_ = protocol.WriteFrame(conn, e, 65536)
			return
		}
		if firstRequest {
			firstRequest = false
			deadline := time.Now().Add(opts.BatchTimeout)
			if deadline.After(trialEnd) {
				deadline = trialEnd
			}
			_ = conn.SetReadDeadline(deadline)
		}
	}
	_ = conn.SetReadDeadline(trialEnd)
	// A second reader observes extra frames while the sole writer schedules
	// responses. A peer half-close is normal; an extra frame ends the trial.
	monitorDone := make(chan struct{})
	go func() {
		defer close(monitorDone)
		var one [1]byte
		for {
			n, err := conn.Read(one[:])
			if n > 0 || (n == 0 && err == nil) || (err != nil && !errors.Is(err, io.EOF)) {
				conn.Close()
				return
			}
			if err != nil {
				return
			}
		}
	}()
	_ = writeResponses(conn, store)
	conn.Close()
	<-monitorDone
}
