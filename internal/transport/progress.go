package transport

import (
	"context"
	"time"
)

type progressKey struct{}
type PayloadPoint struct {
	ElapsedMS float64
	Bytes     uint64
}

func WithProgress(ctx context.Context) context.Context {
	return context.WithValue(ctx, progressKey{}, true)
}
func ProgressEnabled(ctx context.Context) bool {
	enabled, _ := ctx.Value(progressKey{}).(bool)
	return enabled
}

// PrepareProgress bounds allocation before t0. Each worker owns its result slice.
func PrepareProgress(r *Result, enabled bool) {
	if enabled {
		r.Progress = make([]PayloadPoint, 0, (r.BytesExpected+16383)/16384)
	}
}

// RecordProgress observes validated DATA frames. Thresholds crossed inside one
// frame share its read-completion time; this resolution is disclosed in evidence.
func RecordProgress(r *Result, bytes uint64) {
	if r.Progress == nil {
		return
	}
	var last uint64
	if len(r.Progress) > 0 {
		last = r.Progress[len(r.Progress)-1].Bytes
	}
	at := float64(time.Since(r.Timing.Start).Nanoseconds()) / 1e6
	for next := ((last / 16384) + 1) * 16384; next <= bytes; next += 16384 {
		r.Progress = append(r.Progress, PayloadPoint{at, next})
		last = next
	}
	if bytes == r.BytesExpected && last != bytes {
		r.Progress = append(r.Progress, PayloadPoint{at, bytes})
	}
}
