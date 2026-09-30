package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func fixture(t *testing.T, s string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(p, []byte(s), 0600); err != nil {
		t.Fatal(err)
	}
	return p
}
func TestWorkloads(t *testing.T) {
	b, err := os.ReadFile("../../configs/workloads.json")
	if err != nil {
		t.Fatal(err)
	}
	w, err := LoadWorkloads("../../configs/workloads.json")
	if err != nil {
		t.Fatal(err)
	}
	if w.Profiles["bulk"].ResourceCount != 6 || w.Profiles["handshake"].ResourceSizeBytes != 1024 {
		t.Fatal("wrong shared profiles")
	}
	for name, s := range map[string]string{
		"unknown":     strings.Replace(string(b), `"schema_version": 1`, `"surprise": 1, "schema_version": 1`, 1),
		"duplicate":   strings.Replace(string(b), `"schema_version": 1`, `"schema_version": 2, "schema_version": 1`, 1),
		"zero_count":  strings.Replace(string(b), `"resource_count": 6`, `"resource_count": 0`, 1),
		"overflow":    strings.Replace(string(b), `"resource_count": 6`, `"resource_count": 9223372036854775807`, 1),
		"total":       strings.Replace(string(b), `"resource_size_bytes": 1048576`, `"resource_size_bytes": 16777216`, 1),
		"raise_limit": strings.Replace(string(b), `"max_resources": 64`, `"max_resources": 65`, 1),
		"chunk":       strings.Replace(string(b), `"chunk_bytes": 16384`, `"chunk_bytes": 65537`, 1),
		"timeout":     strings.Replace(string(b), `"trial_seconds": 60`, `"trial_seconds": 0`, 1),
		"trailing":    string(b) + `{}`,
		"null":        `null`,
		"oversized":   strings.Repeat(" ", MaxConfigBytes+1),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := LoadWorkloads(fixture(t, s)); err == nil {
				t.Fatal("accepted invalid config")
			}
		})
	}
}
func TestScenarios(t *testing.T) {
	b, err := os.ReadFile("../../configs/scenarios.json")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := LoadScenarios("../../configs/scenarios.json"); err != nil {
		t.Fatal(err)
	}
	for name, s := range map[string]string{
		"egress":         strings.Replace(string(b), "ingress-ifb", "egress-demo", 1),
		"loss":           strings.Replace(string(b), `"loss_downstream_pct": 0`, `"loss_downstream_pct": 101`, 1),
		"rate":           strings.Replace(string(b), `"rate_mbps": 20`, `"rate_mbps": 0`, 1),
		"duplicate_name": strings.Replace(string(b), "rtt50-loss0", "baseline", 1),
		"unknown":        strings.Replace(string(b), `"mtu": 1500`, `"mtuu": 1500`, 1),
		"warmups":        strings.Replace(string(b), `"warmups_per_transport": 2`, `"warmups_per_transport": -1`, 1),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := LoadScenarios(fixture(t, s)); err == nil {
				t.Fatal("accepted invalid scenario")
			}
		})
	}
}
