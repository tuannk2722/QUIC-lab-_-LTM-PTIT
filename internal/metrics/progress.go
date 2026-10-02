package metrics

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"quic-performance-lab/internal/transport"
)

// WriteProgress is called after all readers and timing stop, including failures.
func WriteProgress(dir string, meta TrialMeta, attempts []transport.Attempt, final []transport.Result) error {
	if len(attempts) == 0 {
		attempts = []transport.Attempt{{Results: final}}
	}
	enabled := false
	for _, a := range attempts {
		for _, r := range a.Results {
			enabled = enabled || r.Progress != nil
		}
	}
	if !enabled {
		return nil
	}
	if meta.TraceMode != "evidence" {
		return fmt.Errorf("progress requires evidence trace mode")
	}
	f, err := os.OpenFile(filepath.Join(dir, "progress.csv"), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return err
	}
	w := csv.NewWriter(f)
	err = w.Write([]string{"schema_version", "experiment_id", "run_id", "resource_id", "attempt_index", "elapsed_ms", "payload_bytes_received"})
	for _, a := range attempts {
		for _, r := range a.Results {
			for _, p := range r.Progress {
				if err == nil {
					err = w.Write([]string{"1", meta.ExperimentID, meta.RunID, strconv.Itoa(int(r.ResourceID)), strconv.Itoa(a.Index), fmt.Sprintf("%.9f", p.ElapsedMS), strconv.FormatUint(p.Bytes, 10)})
				}
			}
		}
	}
	w.Flush()
	if err == nil {
		err = w.Error()
	}
	closeErr := f.Close()
	if err == nil {
		err = closeErr
	}
	return err
}
