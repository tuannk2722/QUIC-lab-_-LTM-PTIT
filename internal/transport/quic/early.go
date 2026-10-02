package quic

import (
	"context"
	"crypto/tls"
	"fmt"
	"time"

	"quic-performance-lab/internal/tlsconfig"
	"quic-performance-lab/internal/transport"
	"quic-performance-lab/internal/workload"
)

type SessionOptions struct {
	Mode                   string
	Timeout, TicketTimeout time.Duration
	// Integration harness: change acceptance after obtaining a valid ticket.
	// Production callers leave this nil. No ticket keys/cache are replaced.
	AfterWarmup func() error
}

// RunSession shares the transfer engine with cold clients. Each sequence owns
// a fresh cache. Its prior connection is logged separately from the target.
func RunSession(ctx context.Context, addr string, cfg *tls.Config, expected *workload.Store, opts SessionOptions) transport.Outcome {
	var o transport.Outcome
	if cfg == nil || expected == nil || opts.Timeout <= 0 || opts.TicketTimeout <= 0 || (opts.Mode != "cold" && opts.Mode != "resumed" && opts.Mode != "early") {
		o.Err = fmt.Errorf("invalid session options")
		return o
	}
	client := cfg.Clone()
	client.ClientSessionCache = nil
	if opts.Mode != "cold" {
		cache := tlsconfig.NewTicketCache()
		client.ClientSessionCache = cache
		o.Warmup, _, o.WarmupErr = runBatch(ctx, addr, client, expected, opts.Timeout, false, cache, opts.TicketTimeout)
		o.TicketObserved = o.WarmupErr == nil
		if o.WarmupErr != nil {
			o.Err = fmt.Errorf("ticket warm-up failed: %w", o.WarmupErr)
			// Target was not dialled: publish an explicit failed preparation
			// observation, not the warm-up's latency as target latency.
			o.Results, _, _ = prepare(expected, time.Now())
			end := time.Now()
			for i := range o.Results {
				o.Results[i].Timing.End = end
			}
			return o
		}
		if opts.AfterWarmup != nil {
			if err := opts.AfterWarmup(); err != nil {
				o.Err = err
				return o
			}
		}
	}
	o.Results, o.Attempts, o.Err = runBatch(ctx, addr, client, expected, opts.Timeout, opts.Mode == "early", nil, 0)
	return o
}
