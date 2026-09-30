package metrics

import (
	"fmt"
	"time"

	"quic-performance-lab/internal/transport"
)

// Values are calculated while time.Time still carries its monotonic clock.
// Nil means the event did not occur; no wall-clock timestamp is subtracted.
type StreamTiming struct {
	RequestStartMS      *float64 `json:"request_start_ms"`
	RequestEndMS        *float64 `json:"request_end_ms"`
	FirstByteMS         *float64 `json:"first_byte_ms"`
	TTFBRequestMS       *float64 `json:"ttfb_request_ms"`
	PayloadDoneMS       *float64 `json:"payload_done_ms"`
	CompleteMS          *float64 `json:"complete_ms"`
	CompletionRequestMS *float64 `json:"completion_request_ms"`
}

type RunTiming struct {
	TCPConnectMS   *float64 `json:"tcp_connect_ms"`
	TLSHandshakeMS *float64 `json:"tls_handshake_ms"`
	HandshakeMS    *float64 `json:"handshake_ms"`
	ConnectMS      *float64 `json:"connect_ms"`
	EarlyReadyMS   *float64 `json:"early_ready_ms"`
	TTFAMS         *float64 `json:"ttfa_ms"`
	TransferMS     *float64 `json:"transfer_ms"`
	TotalMS        *float64 `json:"total_ms"`
	ElapsedMS      float64  `json:"elapsed_ms"`
	GoodputMbps    *float64 `json:"goodput_mbps"`
	E2EGoodputMbps *float64 `json:"e2e_goodput_mbps"`
}

func diff(start, end time.Time) (*float64, error) {
	if start.IsZero() || end.IsZero() {
		return nil, nil
	}
	d := end.Sub(start)
	if d < 0 {
		return nil, fmt.Errorf("negative event duration")
	}
	v := float64(d) / float64(time.Millisecond)
	return &v, nil
}

func Stream(t transport.Timing) (StreamTiming, error) {
	var s StreamTiming
	var err error
	if t.Start.IsZero() {
		return s, fmt.Errorf("missing t0")
	}
	for _, f := range []struct {
		dst  **float64
		a, b time.Time
	}{
		{&s.RequestStartMS, t.Start, t.RequestStart},
		{&s.RequestEndMS, t.Start, t.RequestEnd},
		{&s.FirstByteMS, t.Start, t.FirstByte},
		{&s.TTFBRequestMS, t.RequestStart, t.FirstByte},
		{&s.PayloadDoneMS, t.Start, t.PayloadDone},
		{&s.CompleteMS, t.Start, t.Done},
		{&s.CompletionRequestMS, t.RequestStart, t.Done},
	} {
		*f.dst, err = diff(f.a, f.b)
		if err != nil {
			return s, err
		}
	}
	if !t.RequestEnd.IsZero() && t.RequestStart.IsZero() {
		return s, fmt.Errorf("request end without start")
	}
	if !t.FirstByte.IsZero() && t.RequestStart.IsZero() {
		return s, fmt.Errorf("first byte without request")
	}
	if !t.PayloadDone.IsZero() && t.FirstByte.IsZero() {
		return s, fmt.Errorf("payload done without first byte")
	}
	if !t.Done.IsZero() && t.PayloadDone.IsZero() {
		return s, fmt.Errorf("FIN without payload done")
	}
	return s, nil
}

// Run derives trial metrics. Total and goodput require a fully verified batch;
// elapsed remains available for failed attempts.
func Run(transportName string, results []transport.Result, success bool) (RunTiming, []StreamTiming, error) {
	var out RunTiming
	if len(results) == 0 {
		return out, nil, fmt.Errorf("empty result batch")
	}
	start, end := results[0].Timing.Start, results[0].Timing.End
	if start.IsZero() || end.IsZero() {
		return out, nil, fmt.Errorf("missing trial start/end")
	}
	value, err := diff(start, end)
	if err != nil {
		return out, nil, err
	}
	out.ElapsedMS = *value
	streams := make([]StreamTiming, len(results))
	var first, req, all time.Time
	var bytes uint64
	for i, r := range results {
		if !r.Timing.Start.Equal(start) || !r.Timing.End.Equal(end) {
			return out, nil, fmt.Errorf("inconsistent trial clock at resource %d", r.ResourceID)
		}
		streams[i], err = Stream(r.Timing)
		if err != nil {
			return out, nil, fmt.Errorf("resource %d: %w", r.ResourceID, err)
		}
		if !r.Timing.FirstByte.IsZero() && (first.IsZero() || r.Timing.FirstByte.Before(first)) {
			first = r.Timing.FirstByte
		}
		if !r.Timing.RequestStart.IsZero() && (req.IsZero() || r.Timing.RequestStart.Before(req)) {
			req = r.Timing.RequestStart
		}
		if r.Timing.Done.After(all) {
			all = r.Timing.Done
		}
		if success {
			if !r.ChecksumOK || r.BytesReceived != r.BytesExpected || r.Timing.Done.IsZero() {
				return out, nil, fmt.Errorf("successful trial has incomplete resource %d", r.ResourceID)
			}
			bytes += r.BytesReceived
		}
	}
	out.TCPConnectMS, err = diff(start, results[0].Timing.TCPConnected)
	if err != nil {
		return out, nil, err
	}
	out.HandshakeMS, err = diff(start, results[0].Timing.Handshake)
	if err != nil {
		return out, nil, err
	}
	out.ConnectMS = out.HandshakeMS
	out.EarlyReadyMS, err = diff(start, results[0].Timing.EarlyReady)
	if err != nil {
		return out, nil, err
	}
	if transportName == "tcp" {
		out.TLSHandshakeMS, err = diff(results[0].Timing.TCPConnected, results[0].Timing.Handshake)
		if err != nil {
			return out, nil, err
		}
	} else if transportName == "quic" {
		if out.TCPConnectMS != nil {
			return out, nil, fmt.Errorf("QUIC has TCP milestone")
		}
	} else {
		return out, nil, fmt.Errorf("invalid transport %q", transportName)
	}
	out.TTFAMS, err = diff(start, first)
	if err != nil {
		return out, nil, err
	}
	if success {
		if first.IsZero() || req.IsZero() || all.IsZero() {
			return out, nil, fmt.Errorf("successful trial missing timing events")
		}
		out.TransferMS, err = diff(req, all)
		if err != nil {
			return out, nil, err
		}
		out.TotalMS, err = diff(start, all)
		if err != nil {
			return out, nil, err
		}
		if all.After(end) {
			return out, nil, fmt.Errorf("completion after trial end")
		}
		if *out.TransferMS > 0 {
			v := 8 * float64(bytes) / (*out.TransferMS * 1000)
			out.GoodputMbps = &v
		}
		if *out.TotalMS > 0 {
			v := 8 * float64(bytes) / (*out.TotalMS * 1000)
			out.E2EGoodputMbps = &v
		}
	}
	return out, streams, nil
}
