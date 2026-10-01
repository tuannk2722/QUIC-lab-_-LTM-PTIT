package bench

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"quic-performance-lab/internal/config"
	"quic-performance-lab/internal/metrics"
)

type Counts struct {
	Planned   int `json:"n_planned"`
	Invoked   int `json:"n_invoked"`
	Attempted int `json:"n_attempted"` // Full scheduled denominator, including unavailable entries.
	Success   int `json:"n_success"`
	Failed    int `json:"n_failed"`
	Missing   int `json:"n_missing_shards"`
	Measured  int `json:"measured_trials"`
	Warmup    int `json:"warmup_trials"`
}

type Invocation struct {
	SchemaVersion int    `json:"schema_version"`
	RunID         string `json:"run_id"`
	StartedUTC    string `json:"started_utc"`
	EndedUTC      string `json:"ended_utc"`
	ExitCode      *int   `json:"exit_code"`
}

type NetworkCheck struct {
	SchemaVersion int            `json:"schema_version"`
	RunID         string         `json:"run_id"`
	Status        string         `json:"status"`
	Error         string         `json:"error"`
	Details       map[string]any `json:"details"`
}

func FinishInvocation(root string, inv Invocation, code int) error {
	inv.EndedUTC = time.Now().UTC().Format(time.RFC3339Nano)
	inv.ExitCode = &code
	path := filepath.Join(root, "logs", inv.RunID+".invocation.json")
	if err := WriteJSON(path+".completed", inv); err != nil {
		return err
	}
	return os.Rename(path+".completed", path)
}

func Merge(root string) (Counts, error) {
	var counts Counts
	s, err := LoadSchedule(root)
	if err != nil {
		return counts, err
	}
	// Freeze output after one merge. Recovery uses a fresh destination/copy;
	// never rewrite an already-reviewed raw dataset on a second invocation.
	if err := os.Mkdir(filepath.Join(root, "raw"), 0700); err != nil {
		return counts, err
	}
	if err := os.WriteFile(filepath.Join(root, "INCOMPLETE"), []byte("merge not finalized\n"), 0600); err != nil {
		return counts, err
	}
	known := map[string]bool{}
	for _, e := range s.Entries {
		known[e.RunID] = true
	}
	children, err := os.ReadDir(filepath.Join(root, "shards"))
	if err != nil {
		return counts, err
	}
	for _, f := range children {
		if !known[f.Name()] || !f.IsDir() {
			return counts, fmt.Errorf("unscheduled shard %s", f.Name())
		}
	}
	records := make([]metrics.TrialRecord, 0, len(s.Entries))
	sources := map[string]any{}
	for _, e := range s.Entries {
		var inv Invocation
		ip := filepath.Join(root, "logs", e.RunID+".invocation.json")
		invoked := false
		if _, err := os.Stat(ip); err == nil {
			if err := config.DecodeJSON(ip, &inv, config.MaxConfigBytes); err != nil {
				return counts, err
			}
			if inv.SchemaVersion != 1 || inv.RunID != e.RunID {
				return counts, fmt.Errorf("invalid invocation record")
			}
			if _, err := time.Parse(time.RFC3339Nano, inv.StartedUTC); err != nil {
				return counts, err
			}
			invoked = true
			counts.Invoked++
		} else if !os.IsNotExist(err) {
			return counts, err
		}
		shard := filepath.Join(root, "shards", e.RunID)
		var record metrics.TrialRecord
		var source any
		raw := filepath.Join(shard, "raw", e.RunID+".json")
		_, statErr := os.Stat(raw)
		if statErr == nil {
			if err := config.DecodeJSON(raw, &record, config.MaxConfigBytes); err != nil {
				return counts, fmt.Errorf("corrupt shard %s: %w", e.RunID, err)
			}
			if err := RecordMatches(s, e, record); err != nil {
				return counts, err
			}
			hash, err := HashFile(raw)
			if err != nil {
				return counts, err
			}
			source = map[string]any{"raw": filepath.Join("shards", e.RunID, "raw", e.RunID+".json"), "sha256": hash}
			if _, err := os.Stat(filepath.Join(shard, "INCOMPLETE")); err == nil {
				record = failRecord(record, "result_write_error", "shard output was incomplete; original raw retained")
			} else if !os.IsNotExist(err) {
				return counts, err
			}
			if inv.ExitCode != nil && *inv.ExitCode != 0 && record.Run.Success {
				record = failRecord(record, "runner_error", "invocation exited nonzero; original shard retained")
			}
		} else if os.IsNotExist(statErr) {
			counts.Missing++
			code, msg, ts := "not_started", "scheduled entry was not invoked; no latency observation", s.CreatedUTC
			if invoked {
				ts = inv.StartedUTC
				code, msg = "missing_shard", "invocation produced no completed raw shard; no latency observation"
				if inv.ExitCode != nil && *inv.ExitCode == 124 {
					code = "timeout"
				}
				if inv.ExitCode == nil || (inv.ExitCode != nil && (*inv.ExitCode == 130 || *inv.ExitCode == 137 || *inv.ExitCode == 143)) {
					code = "interrupted"
				}
			}
			record = Missing(s, e, code, msg, ts)
			source = map[string]any{"missing": true, "invoked": invoked, "elapsed_observed": false}
		} else {
			return counts, statErr
		}
		if s.Execution == "ingress-ifb" && statErr == nil {
			var check NetworkCheck
			cp := filepath.Join(root, "network", e.RunID+".check.json")
			err := config.DecodeJSON(cp, &check, config.MaxConfigBytes)
			if err != nil || check.SchemaVersion != 1 || check.RunID != e.RunID || check.Status != "PASS" {
				record = failRecord(record, "environment_error", "network before/after verification unavailable or failed; original shard retained")
			}
		}
		if err := WriteJSON(filepath.Join(root, "raw", e.RunID+".json"), record); err != nil {
			return counts, err
		}
		sources[e.RunID] = source
		records = append(records, record)
		counts.Attempted++
		if record.Run.Success {
			counts.Success++
		} else {
			counts.Failed++
		}
		if e.Phase == "measured" {
			counts.Measured++
		} else {
			counts.Warmup++
		}
	}
	counts.Planned = len(s.Entries)
	if err := metrics.WriteAggregate(root, records); err != nil {
		return counts, err
	}
	if err := WriteJSON(filepath.Join(root, "merge.json"), map[string]any{"schema_version": 1, "counts": counts, "sources": sources,
		"failure_policy": "scheduled denominator; original shards retained; missing elapsed=0 is unobserved sentinel; success-only latency with failures reported"}); err != nil {
		return counts, err
	}
	if err := os.Remove(filepath.Join(root, "INCOMPLETE")); err != nil {
		return counts, err
	}
	return counts, nil
}

func failRecord(r metrics.TrialRecord, code, msg string) metrics.TrialRecord {
	r.Run.Success = false
	r.Run.ErrorCode, r.Run.ErrorMessage = code, msg
	r.Run.TotalMS, r.Run.TransferMS, r.Run.GoodputMbps, r.Run.E2EGoodputMbps = nil, nil, nil, nil
	return r
}
