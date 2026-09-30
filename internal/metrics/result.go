package metrics

import (
	"context"
	"errors"
	"fmt"
	"net"
	"strings"
	"time"

	"quic-performance-lab/internal/transport"
)

const SchemaVersion = 1

// RunRecord and StreamRecord mirror schemas/result-records.schema.json v1.
// Pointer fields preserve null instead of converting missing events to zero.
type RunRecord struct {
	SchemaVersion     int     `json:"schema_version"`
	ExperimentID      string  `json:"experiment_id"`
	RunID             string  `json:"run_id"`
	Phase             string  `json:"phase"`
	RepeatIndex       int     `json:"repeat_index"`
	PairID            string  `json:"pair_id"`
	OrderIndex        int     `json:"order_index"`
	TimestampUTC      string  `json:"timestamp_utc"`
	Scenario          string  `json:"scenario"`
	Transport         string  `json:"transport"`
	Mode              string  `json:"mode"`
	TraceMode         string  `json:"trace_mode"`
	NetworkProfile    string  `json:"network_profile"`
	ResourceCount     int     `json:"resource_count"`
	ResourceSizeBytes uint64  `json:"resource_size_bytes"`
	ChunkBytes        uint32  `json:"chunk_bytes"`
	DelayEachWayMS    float64 `json:"delay_each_way_ms"`
	LossDownstreamPct float64 `json:"loss_downstream_pct"`
	LossUpstreamPct   float64 `json:"loss_upstream_pct"`
	RateMbps          float64 `json:"rate_mbps"`
	NetemSeed         *uint64 `json:"netem_seed"`
	BytesExpected     uint64  `json:"bytes_expected"`
	BytesReceived     uint64  `json:"bytes_received"`
	RunTiming
	TLSResumed    *bool  `json:"tls_resumed"`
	Attempted0RTT bool   `json:"attempted_0rtt"`
	Used0RTT      *bool  `json:"used_0rtt"`
	EarlyRejected *bool  `json:"early_rejected"`
	FallbackCount int    `json:"fallback_count"`
	Success       bool   `json:"success"`
	ErrorCode     string `json:"error_code"`
	ErrorMessage  string `json:"error_message"`
}

type StreamRecord struct {
	SchemaVersion     int    `json:"schema_version"`
	ExperimentID      string `json:"experiment_id"`
	RunID             string `json:"run_id"`
	ResourceID        uint32 `json:"resource_id"`
	TransportStreamID *int64 `json:"transport_stream_id"`
	AttemptIndex      int    `json:"attempt_index"`
	StreamTiming
	BytesExpected uint64 `json:"bytes_expected"`
	BytesReceived uint64 `json:"bytes_received"`
	ChecksumOK    *bool  `json:"checksum_ok"`
	Success       bool   `json:"success"`
	ErrorCode     string `json:"error_code"`
	ErrorMessage  string `json:"error_message"`
}

type TrialRecord struct {
	Run     RunRecord      `json:"run"`
	Streams []StreamRecord `json:"streams"`
}

// ProgressRecord reserves the schema v1 evidence layout; collection starts in P11.
type ProgressRecord struct {
	SchemaVersion        int     `json:"schema_version"`
	ExperimentID         string  `json:"experiment_id"`
	RunID                string  `json:"run_id"`
	ResourceID           uint32  `json:"resource_id"`
	AttemptIndex         int     `json:"attempt_index"`
	ElapsedMS            float64 `json:"elapsed_ms"`
	PayloadBytesReceived uint64  `json:"payload_bytes_received"`
}

type TrialMeta struct {
	ExperimentID, RunID, Phase, Scenario, Transport, Mode, TraceMode, NetworkProfile string
	RepeatIndex, OrderIndex                                                          int
	PairID                                                                           string
	ResourceCount                                                                    int
	ResourceSizeBytes                                                                uint64
	ChunkBytes                                                                       uint32
}

func classify(err error) (string, string) {
	if err == nil {
		return "", ""
	}
	code := "transfer_error"
	var netErr net.Error
	switch {
	case errors.Is(err, context.DeadlineExceeded), errors.As(err, &netErr) && netErr.Timeout():
		code = "timeout"
	case errors.Is(err, context.Canceled):
		code = "cancelled"
	case strings.Contains(err.Error(), "checksum"):
		code = "checksum_mismatch"
	case strings.Contains(err.Error(), "QB01"), strings.Contains(err.Error(), "response"), strings.Contains(err.Error(), "FIN"):
		code = "protocol_error"
	}
	msg := strings.ToValidUTF8(err.Error(), "?")
	if len(msg) > 256 {
		msg = msg[:256]
	}
	return code, msg
}

// NewTrial converts the complete transport result, including partial results
// from a failed connection, into N final-attempt resource rows.
func NewTrial(meta TrialMeta, results []transport.Result, transferErr error) (TrialRecord, error) {
	var record TrialRecord
	if meta.ResourceCount < 1 || len(results) != meta.ResourceCount {
		return record, fmt.Errorf("expected %d result slots, got %d", meta.ResourceCount, len(results))
	}
	success := transferErr == nil
	runTiming, streamTimings, err := Run(meta.Transport, results, success)
	if err != nil {
		return record, err
	}
	code, msg := classify(transferErr)
	start := results[0].Timing.Start
	run := RunRecord{SchemaVersion: SchemaVersion, ExperimentID: meta.ExperimentID, RunID: meta.RunID,
		Phase: meta.Phase, RepeatIndex: meta.RepeatIndex, PairID: meta.PairID, OrderIndex: meta.OrderIndex,
		TimestampUTC: start.UTC().Format(time.RFC3339Nano), Scenario: meta.Scenario, Transport: meta.Transport,
		Mode: meta.Mode, TraceMode: meta.TraceMode, NetworkProfile: meta.NetworkProfile,
		ResourceCount: meta.ResourceCount, ResourceSizeBytes: meta.ResourceSizeBytes, ChunkBytes: meta.ChunkBytes,
		BytesExpected: uint64(meta.ResourceCount) * meta.ResourceSizeBytes, RunTiming: runTiming,
		Success: success, ErrorCode: code, ErrorMessage: msg}
	record.Streams = make([]StreamRecord, meta.ResourceCount)
	seen := make(map[uint32]bool, meta.ResourceCount)
	for i, r := range results {
		if r.ResourceID < 1 || int(r.ResourceID) > meta.ResourceCount || seen[r.ResourceID] {
			return TrialRecord{}, fmt.Errorf("duplicate or invalid resource ID %d", r.ResourceID)
		}
		seen[r.ResourceID] = true
		if r.BytesExpected != meta.ResourceSizeBytes {
			return TrialRecord{}, fmt.Errorf("resource %d expected size mismatch", r.ResourceID)
		}
		if r.BytesReceived > r.BytesExpected {
			return TrialRecord{}, fmt.Errorf("resource %d received too many bytes", r.ResourceID)
		}
		run.BytesReceived += r.BytesReceived
		complete := r.Timing.Done.IsZero() == false && r.BytesReceived == r.BytesExpected
		streamSuccess := complete && r.ChecksumOK && r.Err == nil
		var checksum *bool
		if r.ChecksumChecked || r.ChecksumOK {
			v := r.ChecksumOK
			checksum = &v
		}
		streamCode, streamMsg := "", ""
		if !streamSuccess {
			streamCode, streamMsg = code, msg
			if r.Err != nil {
				streamCode, streamMsg = classify(r.Err)
			}
			if streamCode == "" {
				streamCode = "incomplete"
				streamMsg = "resource did not complete"
			}
		}
		record.Streams[r.ResourceID-1] = StreamRecord{SchemaVersion: SchemaVersion, ExperimentID: meta.ExperimentID, RunID: meta.RunID,
			ResourceID: r.ResourceID, TransportStreamID: r.StreamID, AttemptIndex: 0, StreamTiming: streamTimings[i],
			BytesExpected: r.BytesExpected, BytesReceived: r.BytesReceived, ChecksumOK: checksum,
			Success: streamSuccess, ErrorCode: streamCode, ErrorMessage: streamMsg}
	}
	record.Run = run
	return record, nil
}
