package bench

import (
	"context"
	"crypto/tls"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"quic-performance-lab/internal/metrics"
	"quic-performance-lab/internal/transport"
	quictransport "quic-performance-lab/internal/transport/quic"
	"quic-performance-lab/internal/workload"
)

func RunTrial(ctx context.Context, tr, mode, addr string, cfg *tls.Config, store *workload.Store, timeout, ticketTimeout time.Duration) transport.Outcome {
	if tr == "quic" {
		return quictransport.RunSession(ctx, addr, cfg, store, quictransport.SessionOptions{Mode: mode, Timeout: timeout, TicketTimeout: ticketTimeout})
	}
	if mode != "cold" {
		return transport.Outcome{Err: fmt.Errorf("non-cold mode requires QUIC")}
	}
	results, err := RunCold(ctx, tr, addr, cfg, store, timeout)
	return transport.Outcome{Results: results, Err: err}
}

// WriteOutcome publishes canonical final rows, a separately timed ticket
// warm-up and all attempt rows. No bytes from discarded attempts are added.
func WriteOutcome(out string, meta metrics.TrialMeta, o transport.Outcome) (metrics.TrialRecord, error) {
	record, err := metrics.NewTrial(meta, o.Results, o.Err)
	if err != nil {
		return record, err
	}
	if err = metrics.WriteTrial(out, record); err != nil {
		return record, err
	}
	marker := filepath.Join(out, "INCOMPLETE")
	if err = os.WriteFile(marker, []byte("session sidecars pending\n"), 0600); err != nil {
		return record, err
	}
	if len(o.Results) > 0 && o.Results[0].Connection != nil {
		if err = WriteJSON(filepath.Join(out, "connection.json"), o.Results[0].Connection); err != nil {
			return record, err
		}
	}
	if len(o.Warmup) > 0 {
		warmMeta := meta
		warmMeta.RunID = meta.RunID + "_ticket"
		warmMeta.Phase = "warmup"
		warmMeta.Mode = "cold"
		// Preserve the public run_id bound even for a 128-byte input ID.
		if len(warmMeta.RunID) > 128 {
			warmMeta.RunID = "ticket_warmup"
		}
		warmRecord, convertErr := metrics.NewTrial(warmMeta, o.Warmup, o.WarmupErr)
		if convertErr != nil {
			return record, convertErr
		}
		if err = metrics.WriteTrial(filepath.Join(out, "ticket-warmup"), warmRecord); err != nil {
			return record, err
		}
	}
	if meta.Transport == "quic" {
		if err = os.Mkdir(filepath.Join(out, "attempts"), 0700); err != nil {
			return record, err
		}
		type attempt struct {
			Index  int                 `json:"attempt_index"`
			Record metrics.TrialRecord `json:"record"`
		}
		rows := []attempt{}
		for _, a := range o.Attempts {
			r, convertErr := metrics.NewTrial(meta, a.Results, a.Err)
			if convertErr != nil {
				return record, convertErr
			}
			rows = append(rows, attempt{a.Index, r})
		}
		if err = WriteJSON(filepath.Join(out, "attempts", meta.RunID+".json"), map[string]any{
			"schema_version": 1, "run_id": meta.RunID, "ticket_observed": o.TicketObserved, "target_invoked": len(o.Attempts) > 0,
			"clock":    "all target attempts retain original monotonic t0; ticket warm-up has its own t0",
			"attempts": rows}); err != nil {
			return record, err
		}
	}
	if err = metrics.WriteProgress(out, meta, o.Attempts, o.Results); err != nil {
		return record, err
	}
	if len(o.Warmup) > 0 {
		wm := meta
		wm.RunID = meta.RunID + "_ticket"
		if len(wm.RunID) > 128 {
			wm.RunID = "ticket_warmup"
		}
		if err = metrics.WriteProgress(filepath.Join(out, "ticket-warmup"), wm, nil, o.Warmup); err != nil {
			return record, err
		}
	}
	return record, os.Remove(marker)
}
