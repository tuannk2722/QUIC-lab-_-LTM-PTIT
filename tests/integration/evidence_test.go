package integration

import (
	"context"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"

	"quic-performance-lab/internal/bench"
	"quic-performance-lab/internal/metrics"
	"quic-performance-lab/internal/observability"
	"quic-performance-lab/internal/transport"
	quictransport "quic-performance-lab/internal/transport/quic"
)

func TestEvidenceRejectedAttemptProgressAndFlush(t *testing.T) {
	srv, client, _ := fixture(t)
	var key [32]byte
	key[0] = 93
	srv.SetSessionTicketKeys([][32]byte{key})
	root := t.TempDir()
	sm, err := observability.New(filepath.Join(root, "server-qlog"), filepath.Join(root, "server.keylog"))
	if err != nil {
		t.Fatal(err)
	}
	sm.TLS(srv)
	var accept atomic.Bool
	accept.Store(true)
	opts := earlyOptions()
	opts.Evidence = sm
	opts.Accept0RTT = accept.Load
	store := quicStore(t, 6, 32769, 8192)
	addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, opts)
	defer stop()
	cm, err := observability.New(filepath.Join(root, "client-qlog"), filepath.Join(root, "client.keylog"))
	if err != nil {
		t.Fatal(err)
	}
	cm.TLS(client)
	ctx := transport.WithProgress(cm.Context(context.Background(), "rejected", "target"))
	o := quictransport.RunSession(ctx, addr, client, store, quictransport.SessionOptions{Mode: "early", Timeout: 4 * time.Second, TicketTimeout: time.Second, AfterWarmup: func() error { accept.Store(false); return nil }})
	if o.Err != nil {
		t.Fatal(o.Err)
	}
	if len(o.Attempts) != 2 || o.Results[0].AttemptIndex != 1 {
		t.Fatal("attempts missing")
	}
	for _, a := range o.Attempts {
		for _, r := range a.Results {
			if a.Index == 0 && len(r.Progress) != 0 {
				t.Fatal("rejected payload duplicated")
			}
			if a.Index == 1 && (len(r.Progress) != 3 || r.Progress[2].Bytes != 32769) {
				t.Fatal("fallback progress missing")
			}
		}
	}
	t.Logf("rejection: attempts=%d final_resources=%d payload_per_resource=%d fallback_points=%d no_discarded_points=true", len(o.Attempts), len(o.Results), o.Results[0].BytesReceived, len(o.Results[0].Progress))
	meta := metrics.TrialMeta{ExperimentID: "g11", RunID: "rejected", Phase: "evidence", Scenario: "loopback-test", Transport: "quic", Mode: "early", TraceMode: "evidence", NetworkProfile: "loopback-test", ResourceCount: 6, ResourceSizeBytes: 32769, ChunkBytes: 8192}
	if _, err := bench.WriteOutcome(filepath.Join(root, "out"), meta, o); err != nil {
		t.Fatal(err)
	}
	if err := cm.Close(); err != nil {
		t.Fatal(err)
	}
	stop()
	if err := sm.Close(); err != nil {
		t.Fatal(err)
	}
	for _, dir := range []string{"server-qlog", "client-qlog"} {
		files, err := filepath.Glob(filepath.Join(root, dir, "*.sqlog"))
		if err != nil || len(files) != 2 {
			t.Fatal("connection traces missing", files, err)
		}
		for _, p := range files {
			b, err := os.ReadFile(p)
			if err != nil || len(b) < 100 || b[0] != 0x1e {
				t.Fatal("trace not usable", err)
			}
		}
	}
}
