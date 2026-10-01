package cli

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"quic-performance-lab/internal/bench"
	"quic-performance-lab/internal/config"
)

type benchOptions struct {
	plan                                                                                                              bool
	entry, merge, out, experimentID, profile, profiles, scenarios, scenario, execution, addr, ca, serverName, network string
	runs, warmups                                                                                                     int
	seed                                                                                                              uint64
	seedDisabled                                                                                                      bool
	timeout                                                                                                           time.Duration
	seen                                                                                                              map[string]bool
	args                                                                                                              []string
}

func runBench(o benchOptions, w config.Workloads, c config.Scenarios, out, errOut io.Writer) int {
	bad := func(err error) int { fmt.Fprintln(errOut, "invalid input:", err); return 2 }
	runtimeError := func(err error) int { fmt.Fprintln(errOut, err); return 1 }
	if o.merge != "" {
		counts, err := bench.Merge(o.merge)
		if err != nil {
			return runtimeError(err)
		}
		if err := json.NewEncoder(out).Encode(counts); err != nil {
			return runtimeError(err)
		}
		if counts.Failed > 0 {
			return 1
		}
		return 0
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if o.entry != "" {
		for _, flag := range []string{"transport", "scenario", "runs", "warmups", "seed", "disable-netem-seed", "network-profile", "run-id"} {
			if o.seen[flag] {
				return bad(fmt.Errorf("%s is controlled by the immutable entry", flag))
			}
		}
		s, e, root, err := bench.LoadEntry(o.entry)
		if err != nil {
			return bad(err)
		}
		if (o.seen["addr"] && o.addr != s.Addr) || (o.seen["server-name"] && o.serverName != s.ServerName) ||
			(o.seen["timeout"] && int64(o.timeout) != s.TimeoutNS) || (o.seen["profile"] && o.profile != s.Profile) ||
			(o.seen["experiment-id"] && o.experimentID != s.ExperimentID) {
			return bad(fmt.Errorf("entry flags conflict with immutable schedule"))
		}
		if o.out == "" {
			o.out = filepath.Join(root, "shards", e.RunID)
		}
		record, err := bench.ExecuteEntry(ctx, o.entry, o.out, o.profiles, o.scenarios, o.ca, o.network)
		if record.Run.RunID != "" {
			if printErr := json.NewEncoder(out).Encode(record.Run); printErr != nil {
				return runtimeError(printErr)
			}
		}
		if err != nil {
			return runtimeError(err)
		}
		return 0
	}
	if o.network != "" {
		return bad(fmt.Errorf("network-state requires one schedule-entry; use scripts/bench.sh for reset/inspect"))
	}
	if o.experimentID == "" {
		id, err := newID("bulk")
		if err != nil {
			return runtimeError(err)
		}
		o.experimentID = id
	}
	if o.out == "" {
		o.out = filepath.Join("results", o.experimentID)
	}
	names := []string{}
	if !o.plan || o.seen["scenario"] {
		names = append(names, o.scenario)
	} else {
		for _, sc := range c.Scenarios {
			if sc.MainSuite {
				names = append(names, sc.Name)
			}
		}
	}
	execution := o.execution
	if !o.plan {
		execution = "loopback-test"
	}
	s := bench.Schedule{SchemaVersion: 1, ExperimentID: o.experimentID, CreatedUTC: time.Now().UTC().Format(time.RFC3339Nano), Suite: "bulk",
		Profile: o.profile, ScenarioNames: names, Runs: o.runs, Warmups: o.warmups, Seed: o.seed, SeedDisabled: o.seedDisabled, Execution: execution,
		Addr: o.addr, ServerName: o.serverName, TimeoutNS: int64(o.timeout), Workloads: w, Scenarios: c}
	var err error
	s.WorkloadsSHA256, err = bench.HashFile(o.profiles)
	if err != nil {
		return runtimeError(err)
	}
	s.ScenariosSHA256, err = bench.HashFile(o.scenarios)
	if err != nil {
		return runtimeError(err)
	}
	s.CASHA256, err = bench.HashFile(o.ca)
	if err != nil {
		return runtimeError(err)
	}
	if _, err := s.BuildEntries(); err != nil {
		return bad(err)
	}
	if err := bench.WritePlan(o.out, s); err != nil {
		return runtimeError(err)
	}
	for _, f := range []struct{ src, dst, hash string }{{o.profiles, "workloads.json", s.WorkloadsSHA256}, {o.scenarios, "scenarios.json", s.ScenariosSHA256}, {o.ca, "ca.crt", s.CASHA256}} {
		b, err := os.ReadFile(f.src)
		if err != nil {
			return runtimeError(err)
		}
		path := filepath.Join(o.out, "config", f.dst)
		if err := os.WriteFile(path, b, 0600); err != nil {
			return runtimeError(err)
		}
		h, err := bench.HashFile(path)
		if err != nil {
			return runtimeError(err)
		}
		if h != f.hash {
			return runtimeError(fmt.Errorf("config changed while planning"))
		}
	}
	s, err = bench.LoadSchedule(o.out)
	if err != nil {
		return runtimeError(err)
	}
	if err := bench.WriteManifest(o.out, s, Version("bench"), o.args); err != nil {
		return runtimeError(err)
	}
	fmt.Fprintln(errOut, "results:", o.out)
	if o.plan {
		if err := json.NewEncoder(out).Encode(map[string]any{"schedule": filepath.Join(o.out, "schedule.json"), "n_planned": len(s.Entries)}); err != nil {
			return runtimeError(err)
		}
		return 0
	}
	for _, e := range s.Entries {
		if ctx.Err() != nil {
			break
		}
		inv := bench.Invocation{SchemaVersion: 1, RunID: e.RunID, StartedUTC: time.Now().UTC().Format(time.RFC3339Nano)}
		if err := bench.WriteJSON(filepath.Join(o.out, "logs", e.RunID+".invocation.json"), inv); err != nil {
			return runtimeError(err)
		}
		_, err := bench.ExecuteEntry(ctx, filepath.Join(o.out, "entries", e.RunID+".json"), filepath.Join(o.out, "shards", e.RunID), o.profiles, o.scenarios, o.ca, "")
		code := 0
		if err != nil {
			code = 1
			fmt.Fprintln(errOut, e.RunID, err)
		}
		if err := bench.FinishInvocation(o.out, inv, code); err != nil {
			return runtimeError(err)
		}
	}
	counts, err := bench.Merge(o.out)
	if err != nil {
		return runtimeError(err)
	}
	if err := json.NewEncoder(out).Encode(counts); err != nil {
		return runtimeError(err)
	}
	if counts.Failed > 0 || ctx.Err() != nil {
		return 1
	}
	return 0
}
