// Package config loads the shared, bounded lab configuration. It allocates no workload.
package config

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
)

const (
	DefaultProfiles  = "configs/workloads.json"
	DefaultScenarios = "configs/scenarios.json"
	MaxConfigBytes   = 1 << 20
)

type Profile struct {
	ResourceCount     int64 `json:"resource_count"`
	ResourceSizeBytes int64 `json:"resource_size_bytes"`
	ChunkBytes        int64 `json:"chunk_bytes"`
}
type Limits struct {
	MaxResources         int64 `json:"max_resources"`
	MaxResourceSizeBytes int64 `json:"max_resource_size_bytes"`
	MaxTotalBytes        int64 `json:"max_total_bytes"`
	MaxChunkBytes        int64 `json:"max_chunk_bytes"`
	MaxActiveConnections int64 `json:"max_active_connections"`
}
type Timeouts struct {
	HandshakeSeconds  int64 `json:"handshake_seconds"`
	BatchSeconds      int64 `json:"batch_seconds"`
	TrialSeconds      int64 `json:"trial_seconds"`
	TicketWaitSeconds int64 `json:"ticket_wait_seconds"`
}
type Workloads struct {
	SchemaVersion int                `json:"schema_version"`
	Generator     string             `json:"generator"`
	Checksum      string             `json:"checksum"`
	Profiles      map[string]Profile `json:"profiles"`
	Limits        Limits             `json:"limits"`
	Timeouts      Timeouts           `json:"timeouts"`
}
type Scenario struct {
	Name              string  `json:"name"`
	MainSuite         bool    `json:"main_suite"`
	DelayEachWayMS    float64 `json:"delay_each_way_ms"`
	LossDownstreamPct float64 `json:"loss_downstream_pct"`
	LossUpstreamPct   float64 `json:"loss_upstream_pct"`
	RateMbps          float64 `json:"rate_mbps"`
}
type Scenarios struct {
	SchemaVersion         int        `json:"schema_version"`
	DefaultNetworkProfile string     `json:"default_network_profile"`
	MTU                   int        `json:"mtu"`
	QueueLimitPackets     int        `json:"queue_limit_packets"`
	MainRunsPerTransport  int        `json:"main_runs_per_transport"`
	WarmupsPerTransport   int        `json:"warmups_per_transport"`
	BaseSeed              uint64     `json:"base_seed"`
	Scenarios             []Scenario `json:"scenarios"`
}

func decode(path string, dst any) error {
	return DecodeJSON(path, dst, MaxConfigBytes)
}

// DecodeJSON rejects duplicate/unknown keys and bounds allocation before decode.
func DecodeJSON(path string, dst any, limit int64) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	b, err := io.ReadAll(io.LimitReader(f, limit+1))
	if err != nil {
		return err
	}
	if int64(len(b)) > limit {
		return fmt.Errorf("JSON exceeds %d bytes", limit)
	}
	// Reject duplicate keys too: otherwise JSON's last-key-wins hides mistakes.
	if err := uniqueKeys(b); err != nil {
		return err
	}
	d := json.NewDecoder(bytes.NewReader(b))
	d.DisallowUnknownFields()
	if err := d.Decode(dst); err != nil {
		return fmt.Errorf("%s: %w", path, err)
	}
	if err := d.Decode(new(any)); err != io.EOF {
		return fmt.Errorf("%s: trailing JSON", path)
	}
	return nil
}

func LoadWorkloads(path string) (Workloads, error) {
	var w Workloads
	if err := decode(path, &w); err != nil {
		return w, err
	}
	return w, ValidateWorkloads(w)
}

func ValidateWorkloads(w Workloads) error {
	if w.SchemaVersion != 1 || w.Generator != "byte((resource_id + offset) % 256)" || w.Checksum != "sha256" {
		return fmt.Errorf("unsupported workload schema/generator/checksum")
	}
	l := w.Limits
	if l.MaxResources < 1 || l.MaxResources > 64 || l.MaxResourceSizeBytes < 1 || l.MaxResourceSizeBytes > 16<<20 || l.MaxTotalBytes < 1 || l.MaxTotalBytes > 64<<20 || l.MaxChunkBytes < 1 || l.MaxChunkBytes > 64<<10 || l.MaxActiveConnections < 1 || l.MaxActiveConnections > 8 {
		return fmt.Errorf("limits exceed DEMO_SPEC bounds or are missing")
	}
	for _, v := range []int64{w.Timeouts.HandshakeSeconds, w.Timeouts.BatchSeconds, w.Timeouts.TrialSeconds, w.Timeouts.TicketWaitSeconds} {
		if v < 1 || v > 3600 {
			return fmt.Errorf("timeouts must be 1..3600 seconds")
		}
	}
	if len(w.Profiles) == 0 {
		return fmt.Errorf("profiles are required")
	}
	for name, p := range w.Profiles {
		if name == "" || p.ResourceCount < 1 || p.ResourceCount > l.MaxResources || p.ResourceSizeBytes < 1 || p.ResourceSizeBytes > l.MaxResourceSizeBytes || p.ChunkBytes < 1 || p.ChunkBytes > l.MaxChunkBytes {
			return fmt.Errorf("invalid profile %q", name)
		}
		// Division before multiplication prevents overflow even with hostile input.
		if p.ResourceSizeBytes > l.MaxTotalBytes/p.ResourceCount {
			return fmt.Errorf("profile %q exceeds total byte limit", name)
		}
	}
	return nil
}

func LoadScenarios(path string) (Scenarios, error) {
	var s Scenarios
	if err := decode(path, &s); err != nil {
		return s, err
	}
	return s, ValidateScenarios(s)
}

func ValidateScenarios(s Scenarios) error {
	if s.SchemaVersion != 1 || s.DefaultNetworkProfile != "ingress-ifb" || s.MTU != 1500 || s.QueueLimitPackets < 1 || s.QueueLimitPackets > 1000000 || s.MainRunsPerTransport < 1 || s.MainRunsPerTransport > 100000 || s.WarmupsPerTransport < 0 || s.WarmupsPerTransport > 100000 || len(s.Scenarios) == 0 {
		return fmt.Errorf("invalid scenario configuration")
	}
	seen := map[string]bool{}
	for _, v := range s.Scenarios {
		if v.Name == "" || seen[v.Name] {
			return fmt.Errorf("empty or duplicate scenario name %q", v.Name)
		}
		seen[v.Name] = true
		for _, n := range []float64{v.DelayEachWayMS, v.LossDownstreamPct, v.LossUpstreamPct, v.RateMbps} {
			if math.IsNaN(n) || math.IsInf(n, 0) {
				return fmt.Errorf("nonfinite network value")
			}
		}
		if v.DelayEachWayMS < 0 || v.DelayEachWayMS > 3600000 || v.LossDownstreamPct < 0 || v.LossDownstreamPct > 100 || v.LossUpstreamPct < 0 || v.LossUpstreamPct > 100 || v.RateMbps <= 0 || v.RateMbps > 1000000 {
			return fmt.Errorf("invalid network values for %q", v.Name)
		}
	}
	return nil
}
