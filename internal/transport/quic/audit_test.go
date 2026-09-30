package quic

import (
	"context"
	"crypto/tls"
	"errors"
	"net"
	"quic-performance-lab/internal/config"
	"quic-performance-lab/internal/metrics"
	"quic-performance-lab/internal/workload"
	"testing"
	"time"
)

func TestResolveHonorsCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err := resolveUDP(ctx, "example.test:4433", func(ctx context.Context, host string) ([]net.IPAddr, error) {
		<-ctx.Done()
		return nil, ctx.Err()
	})
	if !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
}

func TestResolveFailureRetainsTrial(t *testing.T) {
	w, err := config.LoadWorkloads("../../../configs/workloads.json")
	if err != nil {
		t.Fatal(err)
	}
	store, err := workload.NewStore(w.Profiles["handshake"], w.Limits)
	if err != nil {
		t.Fatal(err)
	}
	rows, failure := RunBatch(context.Background(), "[bad::ip]:4433", &tls.Config{}, store, time.Second)
	if failure == nil || len(rows) != store.Count() {
		t.Fatalf("%v %v", rows, failure)
	}
	record, err := metrics.NewTrial(metrics.TrialMeta{Transport: "quic", ResourceCount: store.Count(), ResourceSizeBytes: uint64(store.Profile().ResourceSizeBytes)}, rows, failure)
	if err != nil || record.Run.Success {
		t.Fatalf("%+v %v", record, err)
	}
}

type timeoutReader struct{}

func (timeoutReader) Read([]byte) (int, error) { return 0, context.DeadlineExceeded }
func TestEOFTimeoutPreservesCause(t *testing.T) {
	err := expectStreamEOF(timeoutReader{})
	var ne net.Error
	if !errors.Is(err, context.DeadlineExceeded) || !errors.As(err, &ne) || !ne.Timeout() {
		t.Fatal(err)
	}
}
