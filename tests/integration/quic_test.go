package integration

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	quicgo "github.com/quic-go/quic-go"
	"quic-performance-lab/internal/config"
	"quic-performance-lab/internal/protocol"
	quictransport "quic-performance-lab/internal/transport/quic"
	"quic-performance-lab/internal/transport/tcp"
	"quic-performance-lab/internal/workload"
)

func quicStore(t *testing.T, count, size, chunk int64) *workload.Store {
	t.Helper()
	w, err := config.LoadWorkloads("../../configs/workloads.json")
	if err != nil {
		t.Fatal(err)
	}
	store, err := workload.NewStore(config.Profile{ResourceCount: count, ResourceSizeBytes: size, ChunkBytes: chunk}, w.Limits)
	if err != nil {
		t.Fatal(err)
	}
	return store
}

func startQUICForTest(t *testing.T, addr string, cfg *tls.Config, store *workload.Store, opts quictransport.ServerOptions) (string, func()) {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	ready, done := make(chan net.Addr, 1), make(chan error, 1)
	go func() { done <- quictransport.Serve(ctx, addr, cfg, store, opts, ready) }()
	select {
	case actual := <-ready:
		var once sync.Once
		return actual.String(), func() {
			once.Do(func() {
				cancel()
				select {
				case err := <-done:
					if err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, quicgo.ErrServerClosed) {
						t.Errorf("QUIC server stop: %v", err)
					}
				case <-time.After(5 * time.Second):
					t.Error("QUIC server did not stop")
				}
			})
		}
	case err := <-done:
		cancel()
		t.Fatalf("QUIC server setup: %v", err)
	case <-time.After(5 * time.Second):
		cancel()
		t.Fatal("QUIC server readiness timeout")
	}
	return "", nil
}

func rawQUICClient(t *testing.T, addr string, cfg *tls.Config) *quicgo.Conn {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	conn, err := quicgo.DialAddr(ctx, addr, cfg, &quicgo.Config{
		Versions: []quicgo.Version{quicgo.Version1}, MaxIncomingStreams: 64, MaxIncomingUniStreams: -1,
	})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = conn.CloseWithError(0, "test done") })
	return conn
}

func openQUICStream(t *testing.T, conn *quicgo.Conn) *quicgo.Stream {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	stream, err := conn.OpenStreamSync(ctx)
	if err != nil {
		t.Fatal(err)
	}
	_ = stream.SetDeadline(time.Now().Add(5 * time.Second))
	return stream
}

func sendQUICRequest(stream *quicgo.Stream, id, count, chunk uint32) error {
	f, err := protocol.RequestFrame(id, count, chunk)
	if err != nil {
		return err
	}
	if err := protocol.WriteFrame(stream, f, chunk); err != nil {
		return err
	}
	return stream.Close()
}

func awaitQUICFailure(t *testing.T, conn *quicgo.Conn) {
	t.Helper()
	select {
	case <-conn.Context().Done():
	case <-time.After(3 * time.Second):
		t.Fatal("invalid QUIC batch did not terminate connection")
	}
}

func readQUICResource(t *testing.T, stream *quicgo.Stream, store *workload.Store, id uint32) {
	t.Helper()
	resource, err := store.Resource(id)
	if err != nil {
		t.Fatal(err)
	}
	chunk := uint32(store.Profile().ChunkBytes)
	receiver, err := protocol.NewReceiver(id, uint64(resource.Size()), resource.SHA256(), chunk)
	if err != nil {
		t.Fatal(err)
	}
	for !receiver.Complete() {
		frame, err := protocol.ReadFrame(stream, chunk)
		if err != nil {
			t.Fatalf("resource %d response: %v", id, err)
		}
		if err := receiver.Accept(frame); err != nil {
			t.Fatalf("resource %d response: %v", id, err)
		}
	}
	var one [1]byte
	if n, err := stream.Read(one[:]); n != 0 || !errors.Is(err, io.EOF) {
		t.Fatalf("resource %d trailing response: n=%d err=%v", id, n, err)
	}
	if err := receiver.Verify(); err != nil {
		t.Fatalf("resource %d checksum: %v", id, err)
	}
}

func TestQUICBulkOneConnectionSixNativeStreamsAndSharedPort(t *testing.T) {
	srv, client, _ := fixture(t)
	store := quicStore(t, 6, 1<<20, 16<<10)
	var tcpAccepted, quicAccepted atomic.Int32
	var mu sync.Mutex
	serverMap := map[uint32]quicgo.StreamID{}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	tcpReady, tcpDone := make(chan net.Addr, 1), make(chan error, 1)
	go func() {
		tcpDone <- tcp.Serve(ctx, "127.0.0.1:0", srv, store, tcp.ServerOptions{
			HandshakeTimeout: 3 * time.Second, BatchTimeout: 3 * time.Second,
			TrialTimeout: 20 * time.Second, MaxConnections: 8,
			OnAccepted: func() { tcpAccepted.Add(1) },
		}, tcpReady)
	}()
	var addr net.Addr
	select {
	case addr = <-tcpReady:
	case err := <-tcpDone:
		t.Fatalf("TCP server setup: %v", err)
	case <-time.After(5 * time.Second):
		t.Fatal("TCP server readiness timeout")
	}
	quicAddr, stopQUIC := startQUICForTest(t, addr.String(), srv, store, quictransport.ServerOptions{
		HandshakeTimeout: 3 * time.Second, BatchTimeout: 3 * time.Second,
		TrialTimeout: 20 * time.Second, MaxConnections: 8,
		OnAccepted: func() { quicAccepted.Add(1) },
		OnStream: func(id uint32, streamID quicgo.StreamID) {
			mu.Lock()
			serverMap[id] = streamID
			mu.Unlock()
		},
	})
	defer stopQUIC()
	if quicAddr != addr.String() {
		t.Fatalf("TCP/UDP endpoint mismatch: TCP=%s UDP=%s", addr, quicAddr)
	}
	tcpResults, err := tcp.RunBatch(context.Background(), addr.String(), client, store, 20*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	results, err := quictransport.RunBatch(context.Background(), addr.String(), client, store, 20*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if tcpAccepted.Load() != 1 || quicAccepted.Load() != 1 || len(tcpResults) != 6 || len(results) != 6 {
		t.Fatalf("accepted TCP=%d QUIC=%d, rows TCP=%d QUIC=%d", tcpAccepted.Load(), quicAccepted.Load(), len(tcpResults), len(results))
	}
	mu.Lock()
	if len(serverMap) != 6 {
		mu.Unlock()
		t.Fatalf("server stream map has %d entries", len(serverMap))
	}
	seen := map[int64]bool{}
	var total uint64
	for i, result := range results {
		id := uint32(i + 1)
		serverID := serverMap[id]
		if result.ResourceID != id || result.StreamID == nil || seen[*result.StreamID] ||
			serverID != quicgo.StreamID(*result.StreamID) || !result.ChecksumOK ||
			!tcpResults[i].ChecksumOK || result.BytesReceived != 1<<20 || tcpResults[i].BytesReceived != result.BytesReceived {
			mu.Unlock()
			t.Fatalf("resource %d QUIC=%+v TCP=%+v server_stream=%d", id, result, tcpResults[i], serverID)
		}
		seen[*result.StreamID] = true
		total += result.BytesReceived
	}
	mu.Unlock()
	cancel()
	select {
	case err := <-tcpDone:
		if err != nil && !errors.Is(err, context.Canceled) {
			t.Fatal(err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("TCP server did not stop")
	}
	t.Logf("one QUIC connection, six native streams, shared TCP/UDP port=%s, verified bytes=%d", addr, total)
}

func TestQUICBarrierAndConcurrentRequests(t *testing.T) {
	srv, client, _ := fixture(t)
	store := quicStore(t, 3, 1024, 256)
	addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, quictransport.ServerOptions{
		HandshakeTimeout: 3 * time.Second, BatchTimeout: 2 * time.Second,
		TrialTimeout: 6 * time.Second, MaxConnections: 8,
	})
	defer stop()
	conn := rawQUICClient(t, addr, client)
	streams := make([]*quicgo.Stream, 3)
	for i := range streams {
		streams[i] = openQUICStream(t, conn)
	}
	if err := sendQUICRequest(streams[0], 1, 3, 256); err != nil {
		t.Fatal(err)
	}
	_ = streams[0].SetReadDeadline(time.Now().Add(150 * time.Millisecond))
	if frame, err := protocol.ReadFrame(streams[0], 256); err == nil || !errors.Is(err, os.ErrDeadlineExceeded) {
		t.Fatalf("response bypassed batch barrier: frame=%+v err=%v", frame, err)
	}
	_ = streams[0].SetReadDeadline(time.Now().Add(5 * time.Second))
	start, errs := make(chan struct{}), make(chan error, 2)
	for i := 1; i < len(streams); i++ {
		i := i
		go func() { <-start; errs <- sendQUICRequest(streams[i], uint32(i+1), 3, 256) }()
	}
	close(start)
	for range 2 {
		if err := <-errs; err != nil {
			t.Fatal(err)
		}
	}
	for i, stream := range streams {
		readQUICResource(t, stream, store, uint32(i+1))
	}
	_ = conn.CloseWithError(0, "complete")
	t.Log("responses waited for the request batch; concurrent streams completed with FIN, EOF and SHA-256")
}

func TestQUICInvalidBatchAndEOFBounded(t *testing.T) {
	srv, client, _ := fixture(t)
	store := quicStore(t, 2, 1024, 1024)
	addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, quictransport.ServerOptions{
		HandshakeTimeout: 3 * time.Second, BatchTimeout: 250 * time.Millisecond,
		TrialTimeout: 3 * time.Second, MaxConnections: 8,
	})
	defer stop()
	for _, tc := range []struct {
		name string
		send func(*testing.T, *quicgo.Conn)
	}{
		{"missing request", func(t *testing.T, conn *quicgo.Conn) {
			if err := sendQUICRequest(openQUICStream(t, conn), 1, 2, 1024); err != nil {
				t.Fatal(err)
			}
		}},
		{"duplicate ID on another stream", func(t *testing.T, conn *quicgo.Conn) {
			for range 2 {
				if err := sendQUICRequest(openQUICStream(t, conn), 1, 2, 1024); err != nil {
					t.Fatal(err)
				}
			}
		}},
		{"invalid first frame", func(t *testing.T, conn *quicgo.Conn) {
			stream := openQUICStream(t, conn)
			if err := protocol.WriteFrame(stream, protocol.MetaFrame(1, 1024, [32]byte{}), 1024); err != nil {
				t.Fatal(err)
			}
			if err := stream.Close(); err != nil {
				t.Fatal(err)
			}
		}},
		{"truncated request EOF", func(t *testing.T, conn *quicgo.Conn) {
			stream := openQUICStream(t, conn)
			if _, err := stream.Write([]byte("QB01")); err != nil {
				t.Fatal(err)
			}
			if err := stream.Close(); err != nil {
				t.Fatal(err)
			}
		}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			conn := rawQUICClient(t, addr, client)
			tc.send(t, conn)
			awaitQUICFailure(t, conn)
		})
	}
}

func TestQUICRequestRequiresSendHalfEOF(t *testing.T) {
	srv, client, _ := fixture(t)
	store := quicStore(t, 1, 1024, 1024)
	addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, quictransport.ServerOptions{
		HandshakeTimeout: 3 * time.Second, BatchTimeout: 250 * time.Millisecond,
		TrialTimeout: time.Second, MaxConnections: 8,
	})
	defer stop()
	conn := rawQUICClient(t, addr, client)
	stream := openQUICStream(t, conn)
	request, _ := protocol.RequestFrame(1, 1, 1024)
	if err := protocol.WriteFrame(stream, request, 1024); err != nil {
		t.Fatal(err)
	}
	_ = stream.SetReadDeadline(time.Now().Add(700 * time.Millisecond))
	if frame, err := protocol.ReadFrame(stream, 1024); err == nil && frame.Type == protocol.Meta {
		t.Fatal("server responded before confirming request send-half EOF")
	}
	awaitQUICFailure(t, conn)
}

func TestQUICExtraStreamAfterBatchAndTrustFailure(t *testing.T) {
	srv, client, _ := fixture(t)
	store := quicStore(t, 1, 16<<20, 64<<10)
	addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, quictransport.ServerOptions{
		HandshakeTimeout: 3 * time.Second, BatchTimeout: time.Second,
		TrialTimeout: 6 * time.Second, MaxConnections: 8,
	})
	defer stop()
	conn := rawQUICClient(t, addr, client)
	first := openQUICStream(t, conn)
	if err := sendQUICRequest(first, 1, 1, 64<<10); err != nil {
		t.Fatal(err)
	}
	frame, err := protocol.ReadFrame(first, 64<<10)
	if err != nil || frame.Type != protocol.Meta {
		t.Fatalf("first response META: frame=%+v err=%v", frame, err)
	}
	extra := openQUICStream(t, conn)
	if err := sendQUICRequest(extra, 1, 1, 64<<10); err != nil {
		t.Fatal(err)
	}
	awaitQUICFailure(t, conn)
	bad := client.Clone()
	bad.RootCAs = x509.NewCertPool()
	if _, err := quictransport.RunBatch(context.Background(), addr, bad, store, 3*time.Second); err == nil {
		t.Fatal("QUIC accepted untrusted server certificate")
	} else if !strings.Contains(err.Error(), "certificate") {
		t.Fatalf("untrusted certificate failed for an unrelated reason: %v", err)
	} else {
		t.Logf("untrusted QUIC certificate rejected: %v", err)
	}
}

func TestQUICServerCancelReleasesWaitingStreams(t *testing.T) {
	srv, client, _ := fixture(t)
	store := quicStore(t, 2, 1024, 1024)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	ready, done := make(chan net.Addr, 1), make(chan error, 1)
	registered := make(chan struct{}, 1)
	go func() {
		done <- quictransport.Serve(ctx, "127.0.0.1:0", srv, store, quictransport.ServerOptions{
			HandshakeTimeout: 3 * time.Second, BatchTimeout: 5 * time.Second,
			TrialTimeout: 10 * time.Second, MaxConnections: 8,
			OnStream: func(uint32, quicgo.StreamID) { registered <- struct{}{} },
		}, ready)
	}()
	var addr net.Addr
	select {
	case addr = <-ready:
	case err := <-done:
		t.Fatalf("QUIC server setup: %v", err)
	case <-time.After(5 * time.Second):
		t.Fatal("QUIC server readiness timeout")
	}
	conn := rawQUICClient(t, addr.String(), client)
	if err := sendQUICRequest(openQUICStream(t, conn), 1, 2, 1024); err != nil {
		t.Fatal(err)
	}
	select {
	case <-registered:
	case <-time.After(3 * time.Second):
		t.Fatal("server did not register waiting stream")
	}
	cancel()
	select {
	case err := <-done:
		if err != nil && !errors.Is(err, context.Canceled) && !errors.Is(err, quicgo.ErrServerClosed) {
			t.Fatal(err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("server cancel left a batch worker waiting")
	}
	awaitQUICFailure(t, conn)
}

func TestQUICClientRejectsEOFBeforeFIN(t *testing.T) {
	srv, client, store := fixture(t)
	listener, err := quicgo.ListenAddr("127.0.0.1:0", srv, &quicgo.Config{Versions: []quicgo.Version{quicgo.Version1}})
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	done := make(chan error, 1)
	release := make(chan struct{})
	defer close(release)
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		conn, err := listener.Accept(ctx)
		if err != nil {
			done <- err
			return
		}
		defer conn.CloseWithError(0, "test done")
		stream, err := conn.AcceptStream(ctx)
		if err != nil {
			done <- err
			return
		}
		defer stream.CancelRead(0)
		if _, err := protocol.ReadFrame(stream, 1024); err != nil {
			done <- err
			return
		}
		var one [1]byte
		if n, err := stream.Read(one[:]); n != 0 || !errors.Is(err, io.EOF) {
			done <- fmt.Errorf("request EOF: n=%d err=%v", n, err)
			return
		}
		resource, _ := store.Resource(1)
		if err := protocol.WriteFrame(stream, protocol.MetaFrame(1, 1024, resource.SHA256()), 1024); err != nil {
			done <- err
			return
		}
		if err := stream.Close(); err != nil {
			done <- err
			return
		}
		done <- nil
		select {
		case <-release:
		case <-ctx.Done():
		}
	}()
	if _, err := quictransport.RunBatch(context.Background(), listener.Addr().String(), client, store, 3*time.Second); err == nil {
		t.Fatal("client accepted response EOF before FIN")
	} else if !strings.Contains(err.Error(), "EOF") {
		t.Fatalf("client failed for an unrelated reason instead of EOF before FIN: %v", err)
	}
	select {
	case err := <-done:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("fake QUIC server did not exit")
	}
}
