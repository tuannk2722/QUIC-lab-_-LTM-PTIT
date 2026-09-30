package metrics

import (
	"encoding/csv"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"quic-performance-lab/internal/transport"
)

func TestRecordsCSVFailureAndNoOverwrite(t *testing.T) {
	base := time.Now()
	meta := TrialMeta{ExperimentID: "exp_test", RunID: "run_test", Phase: "measured", Scenario: "loopback-test", Transport: "tcp", Mode: "cold", TraceMode: "performance", NetworkProfile: "loopback-test", ResourceCount: 2, ResourceSizeBytes: 4, ChunkBytes: 4}
	results := []transport.Result{{ResourceID: 1, BytesExpected: 4, BytesReceived: 4, Timing: transport.Timing{Start: base, TCPConnected: at(base, 1), Handshake: at(base, 2), RequestStart: at(base, 3), RequestEnd: at(base, 4), FirstByte: at(base, 5), PayloadDone: at(base, 6), Done: at(base, 7), End: at(base, 10)}}, {ResourceID: 2, BytesExpected: 4, Timing: transport.Timing{Start: base, TCPConnected: at(base, 1), Handshake: at(base, 2), End: at(base, 10)}}}
	message := "peer said, \"bad\"\nrequest"
	record, err := NewTrial(meta, results, errors.New(message))
	if err != nil {
		t.Fatal(err)
	}
	if record.Run.Success || record.Run.TotalMS != nil || record.Run.BytesReceived != 4 || len(record.Streams) != 2 {
		t.Fatalf("failed row lost: %+v", record)
	}
	if record.Streams[1].RequestStartMS != nil || record.Streams[1].ChecksumOK != nil {
		t.Fatalf("unrequested stream has fake fields: %+v", record.Streams[1])
	}
	dir := filepath.Join(t.TempDir(), "trial")
	if err := WriteTrial(dir, record); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(dir, "INCOMPLETE")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("completed result has incomplete marker: %v", err)
	}
	f, err := os.Open(filepath.Join(dir, "runs.csv"))
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	rows, err := csv.NewReader(f).ReadAll()
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 2 || rows[1][len(rows[1])-1] != message || !strings.Contains(record.Run.ErrorMessage, "\n") {
		t.Fatalf("CSV quoting: %q", rows)
	}
	if err := WriteTrial(dir, record); err == nil {
		t.Fatal("overwrote existing result directory")
	}
	if _, err := NewTrial(meta, []transport.Result{results[0], results[0]}, errors.New(message)); err == nil {
		t.Fatal("duplicate resource accepted")
	}
	blocked := filepath.Join(t.TempDir(), "blocked")
	if err := os.WriteFile(blocked, []byte("file"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := WriteTrial(blocked, record); err == nil {
		t.Fatal("writer failure ignored")
	}
}

type failingWriter struct{}

func (failingWriter) Write([]byte) (int, error) { return 0, io.ErrClosedPipe }

func TestCSVFlushErrorPropagates(t *testing.T) {
	if err := writeCSVRows(failingWriter{}, RunColumns, []any{RunRecord{}}); !errors.Is(err, io.ErrClosedPipe) {
		t.Fatalf("flush error = %v", err)
	}
}

func TestPerResourceFailurePreservesVerifiedSiblings(t *testing.T) {
	base := time.Now()
	timing := transport.Timing{Start: base, RequestStart: at(base, 1), FirstByte: at(base, 2), PayloadDone: at(base, 3), Done: at(base, 4), End: at(base, 5)}
	bad := errors.New("checksum mismatch")
	results := []transport.Result{
		{ResourceID: 1, BytesExpected: 4, BytesReceived: 4, ChecksumChecked: true, ChecksumOK: true, Timing: timing},
		{ResourceID: 2, BytesExpected: 4, BytesReceived: 4, ChecksumChecked: true, Err: bad, Timing: timing},
		{ResourceID: 3, BytesExpected: 4, BytesReceived: 4, ChecksumChecked: true, ChecksumOK: true, Timing: timing},
	}
	record, err := NewTrial(TrialMeta{Transport: "quic", ResourceCount: 3, ResourceSizeBytes: 4}, results, bad)
	if err != nil {
		t.Fatal(err)
	}
	if record.Run.Success || !record.Streams[0].Success || !record.Streams[2].Success || record.Streams[0].ErrorCode != "" {
		t.Fatalf("%+v", record)
	}
	s := record.Streams[1]
	if s.Success || s.ChecksumOK == nil || *s.ChecksumOK || s.ErrorCode != "checksum_mismatch" {
		t.Fatalf("%+v", s)
	}
}
