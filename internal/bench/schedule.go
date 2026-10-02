// Package bench owns immutable schedules and fresh cold trials; it never calls sudo/tc.
package bench

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"reflect"
	"strconv"
	"time"

	"quic-performance-lab/internal/config"
	"quic-performance-lab/internal/metrics"
)

const MaxEntries = 4096
const MaxScheduleBytes = 8 << 20

type Entry struct {
	SchemaVersion   int     `json:"schema_version"`
	ExperimentID    string  `json:"experiment_id"`
	RunID           string  `json:"run_id"`
	Scenario        string  `json:"scenario"`
	Phase           string  `json:"phase"`
	RepeatIndex     int     `json:"repeat_index"`
	PairID          string  `json:"pair_id"`
	OrderIndex      int     `json:"order_index"`
	Transport       string  `json:"transport"`
	Mode            string  `json:"mode"`
	WorkloadProfile string  `json:"workload_profile"`
	NetemSeed       *uint64 `json:"netem_seed"`
	TraceMode       string  `json:"trace_mode"`
	Index           int     `json:"index"`
}

type Schedule struct {
	SchemaVersion   int              `json:"schema_version"`
	ExperimentID    string           `json:"experiment_id"`
	CreatedUTC      string           `json:"created_utc"`
	Suite           string           `json:"suite"`
	Profile         string           `json:"profile"`
	ScenarioNames   []string         `json:"scenario_names"`
	Runs            int              `json:"runs"`
	Warmups         int              `json:"warmups"`
	Seed            uint64           `json:"seed"`
	SeedDisabled    bool             `json:"seed_disabled"`
	Execution       string           `json:"execution"` // ingress-ifb or loopback-test
	Addr            string           `json:"addr"`
	ServerName      string           `json:"server_name"`
	TimeoutNS       int64            `json:"timeout_ns"`
	Workloads       config.Workloads `json:"workloads"`
	Scenarios       config.Scenarios `json:"scenarios"`
	WorkloadsSHA256 string           `json:"workloads_sha256"`
	ScenariosSHA256 string           `json:"scenarios_sha256"`
	CASHA256        string           `json:"ca_sha256"`
	Entries         []Entry          `json:"entries"`
}

type EntryFile struct {
	SchemaVersion  int    `json:"schema_version"`
	ScheduleSHA256 string `json:"schedule_sha256"`
	Entry          Entry  `json:"entry"`
}

func HashFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil {
		return "", err
	}
	if !st.Mode().IsRegular() || st.Size() > MaxScheduleBytes {
		return "", fmt.Errorf("invalid or oversized file: %s", path)
	}
	b, err := io.ReadAll(io.LimitReader(f, MaxScheduleBytes+1))
	if err != nil {
		return "", err
	}
	if len(b) > MaxScheduleBytes {
		return "", fmt.Errorf("file grew beyond limit: %s", path)
	}
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:]), nil
}

func hashValid(h string) bool {
	b, err := hex.DecodeString(h)
	return err == nil && len(b) == sha256.Size && hex.EncodeToString(b) == h
}

// BuildEntries uses a specified SplitMix64 sequence (not a floating RNG API).
// The phase-specific starting order is seeded; subsequent pairs alternate.
func (s Schedule) BuildEntries() ([]Entry, error) {
	if err := config.ValidateWorkloads(s.Workloads); err != nil {
		return nil, err
	}
	if err := config.ValidateScenarios(s.Scenarios); err != nil {
		return nil, err
	}
	factor := 2
	if s.Suite == "handshake" {
		factor = 3
	}
	if !metrics.ValidID(s.ExperimentID) || s.SchemaVersion != 1 || (s.Suite != "bulk" && s.Suite != "handshake") ||
		s.Runs < 1 || s.Warmups < 0 || len(s.ScenarioNames) == 0 ||
		s.Runs > MaxEntries/factor || s.Warmups > MaxEntries/factor ||
		factor*(s.Runs+s.Warmups)*len(s.ScenarioNames) > MaxEntries ||
		(s.Execution != "ingress-ifb" && s.Execution != "loopback-test") ||
		s.TimeoutNS <= 0 || s.TimeoutNS > int64(time.Hour) || s.Addr == "" || s.ServerName == "" {
		return nil, fmt.Errorf("invalid schedule settings (max %d entries)", MaxEntries)
	}
	if _, ok := s.Workloads.Profiles[s.Profile]; !ok {
		return nil, fmt.Errorf("unknown schedule workload")
	}
	if s.Suite == "handshake" {
		p := s.Workloads.Profiles[s.Profile]
		c := s.Scenario("rtt50-loss0")
		if s.Profile != "handshake" || p.ResourceCount != 1 || p.ResourceSizeBytes != 1024 || p.ChunkBytes != 1024 ||
			len(s.ScenarioNames) != 1 || s.ScenarioNames[0] != "rtt50-loss0" || c.DelayEachWayMS != 25 || c.LossDownstreamPct != 0 || c.LossUpstreamPct != 0 || c.RateMbps != 20 {
			return nil, fmt.Errorf("handshake suite requires handshake profile and normative rtt50-loss0")
		}
	}
	host, port, err := net.SplitHostPort(s.Addr)
	portNumber, numberErr := strconv.Atoi(port)
	if err != nil || host == "" || numberErr != nil || portNumber < 1 || portNumber > 65535 {
		return nil, fmt.Errorf("invalid schedule endpoint")
	}
	for _, h := range []string{s.WorkloadsSHA256, s.ScenariosSHA256, s.CASHA256} {
		if !hashValid(h) {
			return nil, fmt.Errorf("invalid schedule config hash")
		}
	}
	known := map[string]bool{}
	for _, c := range s.Scenarios.Scenarios {
		known[c.Name] = true
	}
	seen := map[string]bool{}
	state := s.Seed
	next := func() uint64 {
		state += 0x9e3779b97f4a7c15
		z := state
		z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9
		z = (z ^ (z >> 27)) * 0x94d049bb133111eb
		return z ^ (z >> 31)
	}
	entries := []Entry{}
	seeds := map[uint64]bool{}
	for ci, name := range s.ScenarioNames {
		if !known[name] || seen[name] {
			return nil, fmt.Errorf("invalid/duplicate scenario %q", name)
		}
		seen[name] = true
		for _, phase := range []string{"warmup", "measured"} {
			n := s.Runs
			if phase == "warmup" {
				n = s.Warmups
			}
			startOrder := int(next() & 1)
			for repeat := 0; repeat < n; repeat++ {
				pair := fmt.Sprintf("c%d_%s_%04d", ci, phase, repeat)
				seed := next()
				for seeds[seed] {
					seed = next()
				}
				seeds[seed] = true
				var applied *uint64
				if !s.SeedDisabled {
					applied = &seed
				}
				if s.Suite == "handshake" {
					orders := [][]string{{"cold", "resumed", "early"}, {"resumed", "early", "cold"}, {"early", "cold", "resumed"},
						{"early", "resumed", "cold"}, {"resumed", "cold", "early"}, {"cold", "early", "resumed"}}
					for oi, mode := range orders[(startOrder+repeat)%len(orders)] {
						entries = append(entries, Entry{1, s.ExperimentID, pair + "_quic_" + mode, name, phase, repeat, pair, oi, "quic", mode, s.Profile, applied, "performance", len(entries)})
					}
					continue
				}
				order := []string{"tcp", "quic"}
				if (startOrder+repeat)%2 == 1 {
					order[0], order[1] = order[1], order[0]
				}
				for oi, tr := range order {
					entries = append(entries, Entry{1, s.ExperimentID, pair + "_" + tr, name, phase, repeat, pair, oi, tr, "cold", s.Profile, applied, "performance", len(entries)})
				}
			}
		}
	}
	return entries, nil
}

func LoadSchedule(root string) (Schedule, error) {
	var s Schedule
	if err := config.DecodeJSON(filepath.Join(root, "schedule.json"), &s, MaxScheduleBytes); err != nil {
		return s, err
	}
	if _, err := time.Parse(time.RFC3339Nano, s.CreatedUTC); err != nil {
		return s, err
	}
	expected, err := s.BuildEntries()
	if err != nil {
		return s, err
	}
	if !reflect.DeepEqual(expected, s.Entries) {
		return s, fmt.Errorf("schedule entries differ from deterministic plan")
	}
	return s, nil
}

// WriteJSON publishes a new file without overwrite; tmp files are synced first.
func WriteJSON(path string, value any) error {
	b, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	f, err := os.CreateTemp(filepath.Dir(path), ".publish-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	_, err = f.Write(append(b, '\n'))
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return os.Link(f.Name(), path)
}

func WritePlan(root string, s Schedule) error {
	entries, err := s.BuildEntries()
	if err != nil {
		return err
	}
	s.Entries = entries
	if err := os.Mkdir(root, 0700); err != nil {
		return err
	}
	for _, sub := range []string{"entries", "shards", "network", "probes", "host", "logs", "config"} {
		if err := os.Mkdir(filepath.Join(root, sub), 0700); err != nil {
			return err
		}
	}
	if err := WriteJSON(filepath.Join(root, "schedule.json"), s); err != nil {
		return err
	}
	hash, err := HashFile(filepath.Join(root, "schedule.json"))
	if err != nil {
		return err
	}
	for _, e := range entries {
		if err := WriteJSON(filepath.Join(root, "entries", e.RunID+".json"), EntryFile{1, hash, e}); err != nil {
			return err
		}
	}
	return nil
}

func LoadEntry(path string) (Schedule, Entry, string, error) {
	root := filepath.Dir(filepath.Dir(path))
	s, err := LoadSchedule(root)
	if err != nil {
		return s, Entry{}, root, err
	}
	var f EntryFile
	if err := config.DecodeJSON(path, &f, config.MaxConfigBytes); err != nil {
		return s, f.Entry, root, err
	}
	hash, err := HashFile(filepath.Join(root, "schedule.json"))
	if err != nil {
		return s, f.Entry, root, err
	}
	e := f.Entry
	if filepath.Base(filepath.Dir(path)) != "entries" || filepath.Base(path) != e.RunID+".json" ||
		f.SchemaVersion != 1 || f.ScheduleSHA256 != hash || e.Index < 0 || e.Index >= len(s.Entries) ||
		!reflect.DeepEqual(s.Entries[e.Index], e) {
		return s, e, root, fmt.Errorf("entry is not part of immutable schedule")
	}
	return s, e, root, nil
}

func (s Schedule) Scenario(name string) config.Scenario {
	for _, v := range s.Scenarios.Scenarios {
		if v.Name == name {
			return v
		}
	}
	return config.Scenario{}
}

func (s Schedule) Meta(e Entry) metrics.TrialMeta {
	p, c := s.Workloads.Profiles[s.Profile], s.Scenario(e.Scenario)
	m := metrics.TrialMeta{ExperimentID: s.ExperimentID, RunID: e.RunID, Phase: e.Phase, Scenario: e.Scenario, Transport: e.Transport,
		Mode: e.Mode, TraceMode: e.TraceMode, NetworkProfile: s.Execution, RepeatIndex: e.RepeatIndex, OrderIndex: e.OrderIndex, PairID: e.PairID,
		ResourceCount: int(p.ResourceCount), ResourceSizeBytes: uint64(p.ResourceSizeBytes), ChunkBytes: uint32(p.ChunkBytes)}
	if s.Execution == "ingress-ifb" {
		m.DelayEachWayMS, m.LossDownstreamPct, m.LossUpstreamPct, m.RateMbps = c.DelayEachWayMS, c.LossDownstreamPct, c.LossUpstreamPct, c.RateMbps
		m.NetemSeed = e.NetemSeed
	} else {
		m.Scenario = "loopback-test"
	}
	return m
}

func MatchNetwork(s Schedule, e Entry, n config.NetworkState) error {
	c := s.Scenario(e.Scenario)
	if s.Execution != "ingress-ifb" || n.NetworkProfile != s.Execution || n.Scenario != e.Scenario ||
		n.ConfigSHA256 != s.ScenariosSHA256 || n.DelayEachWayMS != c.DelayEachWayMS || n.LossDownstreamPct != c.LossDownstreamPct ||
		n.LossUpstreamPct != c.LossUpstreamPct || n.RateMbps != c.RateMbps || n.MTU != s.Scenarios.MTU ||
		n.QueueLimitPackets != s.Scenarios.QueueLimitPackets || !reflect.DeepEqual(e.NetemSeed, n.NetemSeed) {
		return fmt.Errorf("actual network differs from schedule entry/config/seed")
	}
	return nil
}
