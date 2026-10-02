package bench

import (
	"context"
	"crypto/tls"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"quic-performance-lab/internal/config"
	"quic-performance-lab/internal/metrics"
	"quic-performance-lab/internal/tlsconfig"
	"quic-performance-lab/internal/transport"
	quictransport "quic-performance-lab/internal/transport/quic"
	tcptransport "quic-performance-lab/internal/transport/tcp"
	"quic-performance-lab/internal/workload"
)

// RunCold is the single transfer dispatch used by both client CLI and bench.
// Each transport creates one fresh connection, with no reusable session cache.
func RunCold(ctx context.Context, tr, addr string, cfg *tls.Config, expected *workload.Store, timeout time.Duration) ([]transport.Result, error) {
	if tr == "tcp" {
		return tcptransport.RunBatch(ctx, addr, cfg, expected, timeout)
	}
	if tr == "quic" {
		return quictransport.RunBatch(ctx, addr, cfg, expected, timeout)
	}
	return nil, fmt.Errorf("invalid cold transport")
}

// ExecuteEntry validates all inputs before t0; input failures leave no fake trial.
// Merge will explicitly represent any invocation that could not produce a shard.
func ExecuteEntry(ctx context.Context, path, out, profiles, scenarios, ca, networkPath string) (metrics.TrialRecord, error) {
	s, e, root, err := LoadEntry(path)
	if err != nil {
		return metrics.TrialRecord{}, err
	}
	for _, f := range []struct{ path, hash string }{{profiles, s.WorkloadsSHA256}, {scenarios, s.ScenariosSHA256}, {ca, s.CASHA256}} {
		h, err := HashFile(f.path)
		if err != nil {
			return metrics.TrialRecord{}, err
		}
		if h != f.hash {
			return metrics.TrialRecord{}, fmt.Errorf("schedule config/CA changed: %s", f.path)
		}
	}
	if filepath.Clean(out) != filepath.Join(root, "shards", e.RunID) {
		return metrics.TrialRecord{}, fmt.Errorf("entry output must be its scheduled shard path")
	}
	if _, err := os.Lstat(out); err == nil {
		return metrics.TrialRecord{}, fmt.Errorf("scheduled shard already exists; refusing duplicate trial")
	} else if !os.IsNotExist(err) {
		return metrics.TrialRecord{}, err
	}
	if _, err := VerifyBuild(filepath.Join(root, "build.json")); err != nil {
		return metrics.TrialRecord{}, err
	}
	if s.Execution == "ingress-ifb" {
		n, err := config.LoadNetworkState(networkPath)
		if err != nil {
			return metrics.TrialRecord{}, err
		}
		if err := MatchNetwork(s, e, n); err != nil {
			return metrics.TrialRecord{}, err
		}
		if err := n.CheckClientNamespace(); err != nil {
			return metrics.TrialRecord{}, err
		}
	} else if networkPath != "" {
		return metrics.TrialRecord{}, fmt.Errorf("loopback plan cannot use network snapshot")
	}
	store, err := workload.NewStore(s.Workloads.Profiles[s.Profile], s.Workloads.Limits)
	if err != nil {
		return metrics.TrialRecord{}, err
	}
	cfg, err := tlsconfig.Client(ca, s.ServerName)
	if err != nil {
		return metrics.TrialRecord{}, err
	}
	// A permanent, atomic claim precedes all network activity. Keep it after
	// errors / process death: a scheduled observation must never be replayed.
	if err := claimEntry(root, e); err != nil {
		return metrics.TrialRecord{}, err
	}
	o := RunTrial(ctx, e.Transport, e.Mode, s.Addr, cfg, store, time.Duration(s.TimeoutNS), time.Duration(s.Workloads.Timeouts.TicketWaitSeconds)*time.Second)
	record, err := WriteOutcome(out, s.Meta(e), o)
	if err != nil {
		return record, err
	}
	return record, o.Err
}

func claimEntry(root string, e Entry) error {
	if _, err := os.Lstat(filepath.Join(root, "raw")); err == nil {
		return fmt.Errorf("aggregate already started; refusing trial")
	} else if !os.IsNotExist(err) {
		return err
	}
	if err := WriteJSON(filepath.Join(root, "logs", e.RunID+".claim.json"), e); err != nil {
		return fmt.Errorf("cannot claim scheduled entry (already claimed or unavailable): %w", err)
	}
	return nil
}

// Missing represents absent/incomplete output, not a measured transfer. The
// non-nullable elapsed_ms uses 0 with an explicit error; latency stays null.
func Missing(s Schedule, e Entry, code, message, timestamp string) metrics.TrialRecord {
	m := s.Meta(e)
	r := metrics.RunRecord{SchemaVersion: 1, ExperimentID: m.ExperimentID, RunID: m.RunID, Phase: m.Phase, RepeatIndex: m.RepeatIndex,
		PairID: m.PairID, OrderIndex: m.OrderIndex, TimestampUTC: timestamp, Scenario: m.Scenario, Transport: m.Transport, Mode: m.Mode,
		TraceMode: m.TraceMode, NetworkProfile: m.NetworkProfile, ResourceCount: m.ResourceCount, ResourceSizeBytes: m.ResourceSizeBytes,
		ChunkBytes: m.ChunkBytes, DelayEachWayMS: m.DelayEachWayMS, LossDownstreamPct: m.LossDownstreamPct, LossUpstreamPct: m.LossUpstreamPct,
		RateMbps: m.RateMbps, NetemSeed: m.NetemSeed, BytesExpected: uint64(m.ResourceCount) * m.ResourceSizeBytes, ErrorCode: code, ErrorMessage: message}
	t := metrics.TrialRecord{Run: r, Streams: make([]metrics.StreamRecord, m.ResourceCount)}
	for i := range t.Streams {
		t.Streams[i] = metrics.StreamRecord{SchemaVersion: 1, ExperimentID: m.ExperimentID, RunID: m.RunID,
			ResourceID: uint32(i + 1), BytesExpected: m.ResourceSizeBytes, ErrorCode: code, ErrorMessage: message}
	}
	return t
}

func RecordMatches(s Schedule, e Entry, r metrics.TrialRecord) error {
	m := s.Meta(e)
	a := r.Run
	if a.SchemaVersion != 1 || a.ExperimentID != m.ExperimentID || a.RunID != m.RunID || a.Phase != m.Phase ||
		a.RepeatIndex != m.RepeatIndex || a.PairID != m.PairID || a.OrderIndex != m.OrderIndex || a.Transport != m.Transport ||
		a.Mode != m.Mode || a.Scenario != m.Scenario || a.TraceMode != m.TraceMode || a.NetworkProfile != m.NetworkProfile ||
		a.ResourceCount != m.ResourceCount || a.ResourceSizeBytes != m.ResourceSizeBytes || a.ChunkBytes != m.ChunkBytes ||
		a.DelayEachWayMS != m.DelayEachWayMS || a.LossDownstreamPct != m.LossDownstreamPct || a.LossUpstreamPct != m.LossUpstreamPct || a.RateMbps != m.RateMbps ||
		(a.NetemSeed == nil) != (m.NetemSeed == nil) || (a.NetemSeed != nil && *a.NetemSeed != *m.NetemSeed) {
		return fmt.Errorf("shard %s differs from schedule/cohort", e.RunID)
	}
	if len(r.Streams) != m.ResourceCount {
		return fmt.Errorf("shard stream count differs")
	}
	var bytes uint64
	for i, v := range r.Streams {
		if v.SchemaVersion != 1 || v.ExperimentID != m.ExperimentID || v.RunID != m.RunID || v.ResourceID != uint32(i+1) ||
			v.BytesExpected != m.ResourceSizeBytes || v.BytesReceived > v.BytesExpected || v.AttemptIndex != a.FallbackCount ||
			(a.Transport == "tcp" && v.TransportStreamID != nil) {
			return fmt.Errorf("invalid shard resource row")
		}
		bytes += v.BytesReceived
		if a.Success && (!v.Success || v.ChecksumOK == nil || !*v.ChecksumOK || v.BytesReceived != v.BytesExpected || v.CompleteMS == nil ||
			(a.Transport == "quic" && v.TransportStreamID == nil)) {
			return fmt.Errorf("invalid successful shard")
		}
	}
	if a.BytesExpected != uint64(m.ResourceCount)*m.ResourceSizeBytes || a.BytesReceived != bytes || a.ElapsedMS < 0 ||
		(a.Success && (a.TotalMS == nil || a.TransferMS == nil || a.ErrorCode != "")) || (!a.Success && a.ErrorCode == "") {
		return fmt.Errorf("invalid shard totals/state")
	}
	return nil
}
