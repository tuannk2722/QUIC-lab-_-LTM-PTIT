package metrics

import (
	"encoding/csv"
	"os"
	"path/filepath"
	"testing"

	"quic-performance-lab/internal/transport"
)

func TestProgressAttemptsAndExclusiveOutput(t *testing.T) {
	dir := t.TempDir()
	meta := TrialMeta{ExperimentID: "e", RunID: "r", TraceMode: "evidence"}
	attempts := []transport.Attempt{{Index: 0, Results: []transport.Result{{ResourceID: 1, Progress: []transport.PayloadPoint{}}}}, {Index: 1, Results: []transport.Result{{ResourceID: 1, Progress: []transport.PayloadPoint{{ElapsedMS: 25, Bytes: 1024}}}}}}
	if err := WriteProgress(dir, meta, attempts, nil); err != nil {
		t.Fatal(err)
	}
	f, err := os.Open(filepath.Join(dir, "progress.csv"))
	if err != nil {
		t.Fatal(err)
	}
	rows, err := csv.NewReader(f).ReadAll()
	f.Close()
	if err != nil || len(rows) != 2 || rows[1][4] != "1" || rows[1][6] != "1024" {
		t.Fatal(rows, err)
	}
	if err := WriteProgress(dir, meta, attempts, nil); err == nil {
		t.Fatal("overwrote existing progress")
	}
	perf := t.TempDir()
	meta.TraceMode = "performance"
	if err := WriteProgress(perf, meta, attempts, nil); err == nil {
		t.Fatal("pooled instrumented data with performance")
	}
	if err := WriteProgress(perf, meta, nil, []transport.Result{{ResourceID: 1}}); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(perf, "progress.csv")); !os.IsNotExist(err) {
		t.Fatal("performance emitted progress")
	}
}
