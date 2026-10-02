package quic

import (
	"context"
	"crypto/tls"
	"fmt"
	"net"
	"sync"
	"time"

	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/workload"

	quicgo "github.com/quic-go/quic-go"
)

type ServerOptions struct {
	Allow0RTT bool
	// Test harness can vary acceptance per connection, keeping TLS keys stable.
	Accept0RTT       func() bool
	HandshakeTimeout time.Duration
	BatchTimeout     time.Duration
	TrialTimeout     time.Duration
	MaxConnections   int
	ConnectionSlots  chan struct{} // optional limiter shared with TCP
	OnAccepted       func()        // optional integration instrumentation
	OnStream         func(resourceID uint32, streamID quicgo.StreamID)
	OnFailure        func(error) // optional integration instrumentation
}

func validServer(cfg *tls.Config, store *workload.Store, opts ServerOptions) error {
	if cfg == nil || store == nil || store.Count() < 1 || store.Count() > maxBidiStreams ||
		opts.HandshakeTimeout <= 0 || opts.BatchTimeout < 0 || opts.TrialTimeout <= 0 ||
		opts.MaxConnections < 1 || opts.MaxConnections > 8 {
		return fmt.Errorf("invalid QUIC server configuration")
	}
	return nil
}

// Serve binds UDP and serves QUIC v1. Readiness is sent only after quic.Listen
// succeeds; dual-listener startup uses ServePacket on prebound UDP instead.
func Serve(ctx context.Context, addr string, cfg *tls.Config, store *workload.Store, opts ServerOptions, ready chan<- net.Addr) error {
	if err := validServer(cfg, store, opts); err != nil {
		return err
	}
	packet, err := net.ListenPacket("udp", addr)
	if err != nil {
		return err
	}
	defer packet.Close()
	return servePacket(ctx, packet, cfg, store, opts, ready)
}

// ServePacket uses an already bound UDP socket. The caller owns packet.Close.
// For dual transport the caller can bind TCP and UDP before starting either.
func ServePacket(ctx context.Context, packet net.PacketConn, cfg *tls.Config, store *workload.Store, opts ServerOptions) error {
	return servePacket(ctx, packet, cfg, store, opts, nil)
}

func servePacket(ctx context.Context, packet net.PacketConn, cfg *tls.Config, store *workload.Store, opts ServerOptions, ready chan<- net.Addr) error {
	if packet == nil {
		return fmt.Errorf("nil QUIC packet socket")
	}
	if err := validServer(cfg, store, opts); err != nil {
		return err
	}
	listener, err := ListenPacket(packet, cfg, opts)
	if err != nil {
		return err
	}
	defer listener.Close()
	if ready != nil {
		select {
		case ready <- listener.Addr():
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	return ServeListener(ctx, listener, store, opts)
}

// ListenPacket completes QUIC listener setup before combined TCP/UDP readiness.
type Listener interface {
	Accept(context.Context) (*quicgo.Conn, error)
	Addr() net.Addr
	Close() error
}

func ListenPacket(packet net.PacketConn, cfg *tls.Config, opts ServerOptions) (Listener, error) {
	if packet == nil || cfg == nil || opts.HandshakeTimeout <= 0 || opts.TrialTimeout <= 0 {
		return nil, fmt.Errorf("invalid QUIC listener configuration")
	}
	qcfg := quicConfig(opts.HandshakeTimeout, opts.TrialTimeout)
	qcfg.Allow0RTT = opts.Allow0RTT
	if opts.Accept0RTT != nil {
		qcfg.GetConfigForClient = func(*quicgo.ClientInfo) (*quicgo.Config, error) {
			selected := qcfg.Clone()
			selected.GetConfigForClient = nil
			selected.Allow0RTT = opts.Accept0RTT()
			return selected, nil
		}
	}
	return quicgo.ListenEarly(packet, cfg, qcfg)
}

// ServeListener serves a prepared listener. The caller owns listener.Close.
func ServeListener(ctx context.Context, listener Listener, store *workload.Store, opts ServerOptions) error {
	if listener == nil || store == nil || store.Count() < 1 || store.Count() > maxBidiStreams || opts.MaxConnections < 1 || opts.MaxConnections > 8 || opts.BatchTimeout < 0 || opts.TrialTimeout <= 0 {
		return fmt.Errorf("invalid QUIC server configuration")
	}
	if opts.BatchTimeout == 0 {
		opts.BatchTimeout = 5 * time.Second
	}
	stopped := make(chan struct{})
	go func() {
		select {
		case <-ctx.Done():
			_ = listener.Close()
		case <-stopped:
		}
	}()
	defer close(stopped)
	sem := opts.ConnectionSlots
	if sem == nil {
		sem = make(chan struct{}, opts.MaxConnections)
	}
	var wg sync.WaitGroup
	defer wg.Wait()
	for {
		conn, acceptErr := listener.Accept(ctx)
		if acceptErr != nil {
			if ctx.Err() != nil {
				return nil
			}
			return acceptErr
		}
		select {
		case sem <- struct{}{}:
			if opts.OnAccepted != nil {
				opts.OnAccepted()
			}
			wg.Go(func() {
				defer func() { <-sem }()
				serveConnection(ctx, conn, store, opts)
			})
		default:
			_ = conn.CloseWithError(appProtocolError, "server connection limit")
		}
	}
}

// batchCoordinator validates request IDs under a short mutex. It never holds
// the mutex while a worker waits for readiness or writes a response.
type batchCoordinator struct {
	mu        sync.Mutex
	batch     *protocol.Batch
	count     int
	confirmed int
	ready     chan struct{}
	closed    bool
	err       error
	timer     *time.Timer
	cancel    context.CancelFunc
	conn      *quicgo.Conn
	opts      ServerOptions
}

func newBatchCoordinator(conn *quicgo.Conn, store *workload.Store, opts ServerOptions, cancel context.CancelFunc) (*batchCoordinator, error) {
	batch, err := protocol.NewBatch(uint32(store.Count()), uint32(store.Profile().ChunkBytes))
	if err != nil {
		return nil, err
	}
	return &batchCoordinator{batch: batch, count: store.Count(), ready: make(chan struct{}), cancel: cancel, conn: conn, opts: opts}, nil
}

func (b *batchCoordinator) register(f protocol.Frame) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		return fmt.Errorf("batch already closed")
	}
	if err := b.batch.Register(f); err != nil {
		return err
	}
	if b.timer == nil {
		b.timer = time.AfterFunc(b.opts.BatchTimeout, b.timeout)
	}
	return nil
}

func (b *batchCoordinator) confirmEOF() {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		return
	}
	b.confirmed++
	if b.batch.Complete() && b.confirmed == b.count {
		b.closed = true
		if b.timer != nil {
			b.timer.Stop()
		}
		close(b.ready)
	}
}

func (b *batchCoordinator) fail(err error) {
	b.mu.Lock()
	if b.err != nil {
		b.mu.Unlock()
		return
	}
	b.err = err
	if !b.closed {
		b.closed = true
		if b.timer != nil {
			b.timer.Stop()
		}
		close(b.ready)
	}
	b.mu.Unlock()
	if b.opts.OnFailure != nil {
		b.opts.OnFailure(err)
	}
	b.cancel()
	_ = b.conn.CloseWithError(appProtocolError, "QB01 batch or stream failure")
}

func (b *batchCoordinator) timeout() {
	b.mu.Lock()
	if b.closed {
		b.mu.Unlock()
		return
	}
	b.err = fmt.Errorf("request batch timeout")
	b.closed = true
	close(b.ready)
	b.mu.Unlock()
	b.cancel()
	_ = b.conn.CloseWithError(appProtocolError, "request batch timeout")
}

func (b *batchCoordinator) wait(ctx context.Context) error {
	select {
	case <-b.ready:
		b.mu.Lock()
		err := b.err
		b.mu.Unlock()
		return err
	case <-ctx.Done():
		return ctx.Err()
	}
}

func serveConnection(parent context.Context, conn *quicgo.Conn, store *workload.Store, opts ServerOptions) {
	ctx, cancel := context.WithTimeout(parent, opts.TrialTimeout)
	defer cancel()
	defer conn.CloseWithError(0, "trial complete")
	coordinator, err := newBatchCoordinator(conn, store, opts, cancel)
	if err != nil {
		return
	}
	stop := make(chan struct{})
	go func() {
		select {
		case <-ctx.Done():
			_ = conn.CloseWithError(appProtocolError, "trial deadline or cancellation")
		case <-stop:
		}
	}()
	defer close(stop)
	deadline, _ := ctx.Deadline()
	var workers sync.WaitGroup
	accepted := 0
	for {
		stream, acceptErr := conn.AcceptStream(ctx)
		if acceptErr != nil {
			if ctx.Err() == nil && accepted < store.Count() {
				coordinator.fail(fmt.Errorf("stream accept before batch complete: %w", acceptErr))
			}
			break
		}
		accepted++
		if accepted > store.Count() {
			stream.CancelRead(streamProtocolError)
			stream.CancelWrite(streamProtocolError)
			coordinator.fail(fmt.Errorf("extra stream after batch registration"))
			break
		}
		_ = stream.SetDeadline(deadline)
		workers.Go(func() { serveStream(ctx, stream, store, coordinator, opts) })
	}
	workers.Wait()
}

func serveStream(ctx context.Context, stream *quicgo.Stream, store *workload.Store, batch *batchCoordinator, opts ServerOptions) {
	complete := false
	defer func() {
		if !complete {
			stream.CancelRead(streamProtocolError)
			stream.CancelWrite(streamProtocolError)
		}
	}()
	chunk := uint32(store.Profile().ChunkBytes)
	f, err := protocol.ReadFrame(stream, chunk)
	if err != nil {
		batch.fail(fmt.Errorf("request frame: %w", err))
		return
	}
	if err := batch.register(f); err != nil {
		batch.fail(fmt.Errorf("request registration: %w", err))
		return
	}
	if opts.OnStream != nil {
		opts.OnStream(f.ResourceID, stream.StreamID())
	}
	if err := expectStreamEOF(stream); err != nil {
		batch.fail(fmt.Errorf("request stream EOF: %w", err))
		return
	}
	batch.confirmEOF()
	if err := batch.wait(ctx); err != nil {
		return
	}
	resource, err := store.Resource(f.ResourceID)
	if err != nil {
		batch.fail(err)
		return
	}
	if err := writeResponse(stream, resource, chunk); err != nil {
		batch.fail(fmt.Errorf("write response: %w", err))
		return
	}
	complete = true
}
