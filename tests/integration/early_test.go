package integration

import (
	"context"
	"crypto/tls"
	"errors"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"

	quicgo "github.com/quic-go/quic-go"

	"quic-performance-lab/internal/bench"
	"quic-performance-lab/internal/metrics"
	quictransport "quic-performance-lab/internal/transport/quic"
)

func earlyOptions() quictransport.ServerOptions {
	return quictransport.ServerOptions{Allow0RTT: true, HandshakeTimeout: time.Second, BatchTimeout: time.Second, TrialTimeout: 5 * time.Second, MaxConnections: 8}
}

func sessionEvidencePath(t *testing.T, name string) string {
	t.Helper()
	if root := os.Getenv("QUICLAB_G10_RECORDS"); root != "" {
		return filepath.Join(root, name)
	}
	return filepath.Join(t.TempDir(), "trial")
}

func TestSessionColdResumedEarlyActualState(t *testing.T) {
	srv, client, _ := fixture(t)
	store := quicStore(t, 1, 1024, 1024)
	addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, earlyOptions())
	defer stop()
	for _, mode := range []string{"cold", "resumed", "early"} {
		t.Run(mode, func(t *testing.T) {
			o := quictransport.RunSession(context.Background(), addr, client, store, quictransport.SessionOptions{Mode: mode, Timeout: 3 * time.Second, TicketTimeout: time.Second})
			if o.Err != nil {
				t.Fatal(o.Err)
			}
			r := o.Results[0]
			state := r.Connection
			if state == nil || state.DidResume != (mode != "cold") || state.Used0RTT == nil || *state.Used0RTT != (mode == "early") {
				t.Fatalf("actual state %+v", state)
			}
			if r.Session.FallbackCount != 0 || r.AttemptIndex != 0 || !r.ChecksumOK || r.BytesReceived != 1024 {
				t.Fatalf("result %+v", r)
			}
			if mode != "cold" && (!o.TicketObserved || len(o.Warmup) != 1 || !o.Warmup[0].Timing.Start.Before(r.Timing.Start)) {
				t.Fatal("ticket/prior sequence invalid")
			}
			if mode == "early" && (r.Timing.EarlyReady.IsZero() || !r.Timing.RequestEnd.Before(r.Timing.Handshake)) {
				t.Fatal("request did not enqueue before observed handshake")
			}
			meta := metrics.TrialMeta{ExperimentID: "g10", RunID: mode, Phase: "measured", Scenario: "loopback-test", Transport: "quic", Mode: mode, TraceMode: "performance", NetworkProfile: "loopback-test", ResourceCount: 1, ResourceSizeBytes: 1024, ChunkBytes: 1024}
			if _, err := bench.WriteOutcome(sessionEvidencePath(t, mode), meta, o); err != nil {
				t.Fatal(err)
			}
			t.Logf("mode=%s resume=%t used0rtt=%t ticket=%t request_minus_handshake=%v bytes=%d", mode, state.DidResume, *state.Used0RTT, o.TicketObserved, r.Timing.RequestStart.Sub(r.Timing.Handshake), r.BytesReceived)
		})
	}
}

func TestSessionRejectedValidTicketSingleReplaySixWorkers(t *testing.T) {
	srv, client, _ := fixture(t)
	// Keep the same valid TLS keys and ALPN for both connections.
	var key [32]byte
	key[0] = 17
	srv.SetSessionTicketKeys([][32]byte{key})
	var accept atomic.Bool
	accept.Store(true)
	var connections, requests atomic.Int32
	opts := earlyOptions()
	opts.Accept0RTT = accept.Load
	opts.OnAccepted = func() { connections.Add(1) }
	opts.OnStream = func(uint32, quicgo.StreamID) { requests.Add(1) }
	opts.OnFailure = func(err error) { t.Logf("server batch failure: %v", err) }
	store := quicStore(t, 6, 1024, 1024)
	addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, opts)
	defer stop()
	o := quictransport.RunSession(context.Background(), addr, client, store, quictransport.SessionOptions{Mode: "early", Timeout: 3 * time.Second, TicketTimeout: time.Second, AfterWarmup: func() error { accept.Store(false); return nil }})
	if o.Err != nil {
		t.Fatal(o.Err)
	}
	if !o.TicketObserved || len(o.Attempts) != 2 || o.Attempts[0].Err == nil || o.Attempts[1].Err != nil {
		t.Fatalf("attempts %+v", o.Attempts)
	}
	for _, r := range o.Results {
		if !r.Connection.DidResume || r.Connection.Used0RTT == nil || *r.Connection.Used0RTT || r.Session.EarlyRejected == nil || !*r.Session.EarlyRejected || r.Session.FallbackCount != 1 || r.AttemptIndex != 1 || r.BytesReceived != 1024 || !r.ChecksumOK {
			t.Fatalf("fallback %+v", r)
		}
		old := o.Attempts[0].Results[r.ResourceID-1]
		if !r.Timing.Start.Equal(old.Timing.Start) || !r.Timing.RequestStart.After(old.Timing.End) {
			t.Fatal("retry reset t0 or raced old worker")
		}
	}
	if connections.Load() != 2 || requests.Load() != 12 {
		t.Fatalf("duplicate fallback connections=%d requests=%d", connections.Load(), requests.Load())
	}
	meta := metrics.TrialMeta{ExperimentID: "g10", RunID: "rejected", Phase: "measured", Scenario: "loopback-test", Transport: "quic", Mode: "early", TraceMode: "performance", NetworkProfile: "loopback-test", ResourceCount: 6, ResourceSizeBytes: 1024, ChunkBytes: 1024}
	record, err := bench.WriteOutcome(sessionEvidencePath(t, "rejected"), meta, o)
	if err != nil {
		t.Fatal(err)
	}
	if record.Run.BytesReceived != 6144 || record.Run.FallbackCount != 1 || *record.Run.Used0RTT {
		t.Fatal("fallback final metrics incorrect")
	}
	t.Logf("valid-ticket rejection: DidResume=true Used0RTT=false fallback=1 attempts=2 requests=%d final_bytes=%d", requests.Load(), record.Run.BytesReceived)
}

func TestSessionTicketTimeoutHandshakeFailureAndCancel(t *testing.T) {
	for _, kind := range []string{"missing_ticket", "target_handshake_failure", "target_cancel"} {
		t.Run(kind, func(t *testing.T) {
			srv, client, _ := fixture(t)
			store := quicStore(t, 1, 1024, 1024)
			var fail atomic.Bool
			if kind == "missing_ticket" {
				srv.SessionTicketsDisabled = true
			}
			if kind == "target_handshake_failure" {
				srv.GetConfigForClient = func(*tls.ClientHelloInfo) (*tls.Config, error) {
					if fail.Load() {
						return nil, errors.New("intentional handshake failure")
					}
					return nil, nil
				}
			}
			addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, earlyOptions())
			defer stop()
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			opts := quictransport.SessionOptions{Mode: "early", Timeout: 2 * time.Second, TicketTimeout: 50 * time.Millisecond, AfterWarmup: func() error {
				if kind == "target_cancel" {
					cancel()
				}
				fail.Store(true)
				return nil
			}}
			start := time.Now()
			o := quictransport.RunSession(ctx, addr, client, store, opts)
			if o.Err == nil || time.Since(start) > 3*time.Second || len(o.Results) != 1 {
				t.Fatalf("unbounded/fake success: %+v", o)
			}
			if kind == "missing_ticket" && (o.TicketObserved || len(o.Attempts) != 0 || !errors.Is(o.Err, context.DeadlineExceeded)) {
				t.Fatal("missing ticket dialled target")
			}
			if kind == "target_cancel" && !errors.Is(o.Err, context.Canceled) {
				t.Fatal("lost cancellation cause")
			}
			if o.Results[0].Session != nil && o.Results[0].Session.FallbackCount != 0 {
				t.Fatal("handshake failure/cancel replayed request")
			}
			meta := metrics.TrialMeta{ExperimentID: "g10", RunID: kind, Phase: "measured", Scenario: "loopback-test", Transport: "quic", Mode: "early", TraceMode: "performance", NetworkProfile: "loopback-test", ResourceCount: 1, ResourceSizeBytes: 1024, ChunkBytes: 1024}
			if _, err := bench.WriteOutcome(sessionEvidencePath(t, kind), meta, o); err != nil {
				t.Fatal(err)
			}
			t.Logf("%s bounded error=%v", kind, o.Err)
		})
	}
}
