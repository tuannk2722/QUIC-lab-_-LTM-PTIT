package integration

import (
	"context"
	"net"
	"sync/atomic"
	"testing"
	"time"

	"quic-performance-lab/internal/bench"
	"quic-performance-lab/internal/metrics"
	quictransport "quic-performance-lab/internal/transport/quic"
)

func TestBenchColdUsesFreshConnectionsAndActualTLS(t *testing.T) {
	srv, client, store := fixture(t)
	var accepted atomic.Int32
	addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, quictransport.ServerOptions{HandshakeTimeout: time.Second, BatchTimeout: time.Second,
		TrialTimeout: time.Second, MaxConnections: 8, OnAccepted: func() { accepted.Add(1) }})
	defer stop()
	for repeat := 0; repeat < 3; repeat++ {
		results, err := bench.RunCold(context.Background(), "quic", addr, client, store, time.Second)
		if err != nil {
			t.Fatal(err)
		}
		info := results[0].Connection
		if info == nil || info.DidResume || info.Used0RTT == nil || *info.Used0RTT || info.TLSVersion != "TLS 1.3" || info.ALPN != "quicbench/1" ||
			info.SendBufferBytes == nil || info.ReceiveBufferBytes == nil {
			t.Fatalf("actual connection %+v", info)
		}
		if !results[0].ChecksumOK {
			t.Fatal("checksum")
		}
	}
	if accepted.Load() != 3 {
		t.Fatalf("reused connection: accepted=%d", accepted.Load())
	}
}

func TestBenchColdDeadlineAndCancelKeepFailureSlots(t *testing.T) {
	_, client, store := fixture(t)
	for _, tr := range []string{"tcp", "quic"} {
		for _, cancelled := range []bool{false, true} {
			t.Run(tr+map[bool]string{false: "/deadline", true: "/cancel"}[cancelled], func(t *testing.T) {
				ctx, cancel := context.WithCancel(context.Background())
				defer cancel()
				addr, closePeer := blackholePeer(t, tr)
				defer closePeer()
				timeout := 60 * time.Millisecond
				if cancelled {
					timeout = time.Second
					time.AfterFunc(20*time.Millisecond, cancel)
				}
				start := time.Now()
				results, err := bench.RunCold(ctx, tr, addr, client.Clone(), store, timeout)
				if err == nil || len(results) != store.Count() || time.Since(start) > 2*time.Second {
					t.Fatalf("deadline/cancel did not finish: %v", err)
				}
				meta := metrics.TrialMeta{ExperimentID: "unit_bench", RunID: "failure", Phase: "measured", Transport: tr, Mode: "cold", Scenario: "loopback-test",
					NetworkProfile: "loopback-test", TraceMode: "performance", ResourceCount: store.Count(), ResourceSizeBytes: uint64(store.Profile().ResourceSizeBytes), ChunkBytes: uint32(store.Profile().ChunkBytes)}
				r, e := metrics.NewTrial(meta, results, err)
				if e != nil || r.Run.Success || len(r.Streams) != store.Count() || r.Run.TotalMS != nil || r.Run.GoodputMbps != nil || r.Run.ElapsedMS <= 0 {
					t.Fatalf("failure representation %+v %v", r.Run, e)
				}
				if r.Run.ErrorCode != "timeout" && r.Run.ErrorCode != "cancelled" {
					t.Fatalf("unstable failure code %s: %v", r.Run.ErrorCode, err)
				}
			})
		}
	}
}

func blackholePeer(t *testing.T, tr string) (string, func()) {
	t.Helper()
	if tr == "quic" {
		p, err := net.ListenPacket("udp", "127.0.0.1:0")
		if err != nil {
			t.Fatal(err)
		}
		return p.LocalAddr().String(), func() { p.Close() }
	}
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	done := make(chan struct{})
	accepted := make(chan net.Conn, 1)
	go func() {
		c, err := l.Accept()
		if err == nil {
			accepted <- c
			<-done
			c.Close()
		}
	}()
	return l.Addr().String(), func() {
		close(done)
		l.Close()
		select {
		case c := <-accepted:
			c.Close()
		default:
		}
	}
}
