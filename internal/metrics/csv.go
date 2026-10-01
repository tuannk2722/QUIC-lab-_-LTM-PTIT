package metrics

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

var safeID = regexp.MustCompile(`^[A-Za-z0-9_-]{1,128}$`)

func ValidID(id string) bool { return safeID.MatchString(id) }

var RunColumns = strings.Split("schema_version,experiment_id,run_id,phase,repeat_index,pair_id,order_index,timestamp_utc,scenario,transport,mode,trace_mode,network_profile,resource_count,resource_size_bytes,chunk_bytes,delay_each_way_ms,loss_downstream_pct,loss_upstream_pct,rate_mbps,netem_seed,bytes_expected,bytes_received,tcp_connect_ms,tls_handshake_ms,handshake_ms,connect_ms,early_ready_ms,ttfa_ms,transfer_ms,total_ms,elapsed_ms,goodput_mbps,e2e_goodput_mbps,tls_resumed,attempted_0rtt,used_0rtt,early_rejected,fallback_count,success,error_code,error_message", ",")
var StreamColumns = strings.Split("schema_version,experiment_id,run_id,resource_id,transport_stream_id,attempt_index,request_start_ms,request_end_ms,first_byte_ms,ttfb_request_ms,payload_done_ms,complete_ms,completion_request_ms,bytes_expected,bytes_received,checksum_ok,success,error_code,error_message", ",")
var ProgressColumns = strings.Split("schema_version,experiment_id,run_id,resource_id,attempt_index,elapsed_ms,payload_bytes_received", ",")

func fields(value any, columns []string) ([]string, error) {
	b, err := json.Marshal(value)
	if err != nil {
		return nil, err
	}
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.UseNumber()
	var row map[string]any
	if err := dec.Decode(&row); err != nil {
		return nil, err
	}
	if len(row) != len(columns) {
		return nil, fmt.Errorf("record fields %d != columns %d", len(row), len(columns))
	}
	out := make([]string, len(columns))
	for i, name := range columns {
		v, ok := row[name]
		if !ok {
			return nil, fmt.Errorf("missing column %s", name)
		}
		switch v := v.(type) {
		case nil:
			out[i] = ""
		case string:
			out[i] = v
		case json.Number:
			out[i] = string(v)
		case bool:
			if v {
				out[i] = "true"
			} else {
				out[i] = "false"
			}
		default:
			return nil, fmt.Errorf("unsupported column %s type %T", name, v)
		}
	}
	return out, nil
}

func writeCSV(path string, columns []string, values []any) error {
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	writeErr := writeCSVRows(f, columns, values)
	if writeErr == nil {
		writeErr = f.Sync()
	}
	closeErr := f.Close()
	if writeErr != nil {
		return writeErr
	}
	return closeErr
}

func writeCSVRows(dst io.Writer, columns []string, values []any) error {
	w := csv.NewWriter(dst)
	writeErr := w.Write(columns)
	for _, v := range values {
		if writeErr != nil {
			break
		}
		var row []string
		row, writeErr = fields(v, columns)
		if writeErr == nil {
			writeErr = w.Write(row)
		}
	}
	w.Flush()
	if writeErr == nil {
		writeErr = w.Error()
	}
	return writeErr
}

// WriteTrial owns the result directory and writes raw JSON first. If a CSV
// flush/sync/close fails, the raw record stays for diagnosis and the caller
// receives a nonzero error; no prior experiment is appended or overwritten.
func WriteTrial(dir string, record TrialRecord) error {
	if !ValidID(record.Run.ExperimentID) || !ValidID(record.Run.RunID) {
		return fmt.Errorf("invalid experiment/run ID")
	}
	if dir == "" {
		return fmt.Errorf("empty result directory")
	}
	if err := os.Mkdir(dir, 0700); err != nil {
		return err
	}
	marker := filepath.Join(dir, "INCOMPLETE")
	if err := os.WriteFile(marker, []byte("result write did not finish\n"), 0600); err != nil {
		return err
	}
	rawDir := filepath.Join(dir, "raw")
	if err := os.Mkdir(rawDir, 0700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(record, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	raw := filepath.Join(rawDir, record.Run.RunID+".json")
	tmp := raw + ".tmp"
	f, err := os.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	_, writeErr := f.Write(data)
	if writeErr == nil {
		writeErr = f.Sync()
	}
	closeErr := f.Close()
	if writeErr != nil {
		return writeErr
	}
	if closeErr != nil {
		return closeErr
	}
	if err := os.Rename(tmp, raw); err != nil {
		return err
	}
	if err := writeCSV(filepath.Join(dir, "runs.csv"), RunColumns, []any{record.Run}); err != nil {
		return err
	}
	streams := make([]any, len(record.Streams))
	for i := range record.Streams {
		streams[i] = record.Streams[i]
	}
	if err := writeCSV(filepath.Join(dir, "streams.csv"), StreamColumns, streams); err != nil {
		return err
	}
	return os.Remove(marker)
}

// WriteAggregate is called once by merge. Raw files are already published;
// INCOMPLETE remains if any CSV flush/sync/close or finalization fails.
func WriteAggregate(dir string, records []TrialRecord) error {
	runs := make([]any, len(records))
	streams := []any{}
	for i, r := range records {
		runs[i] = r.Run
		for _, s := range r.Streams {
			streams = append(streams, s)
		}
	}
	if err := writeCSV(filepath.Join(dir, "runs.csv"), RunColumns, runs); err != nil {
		return err
	}
	return writeCSV(filepath.Join(dir, "streams.csv"), StreamColumns, streams)
}
