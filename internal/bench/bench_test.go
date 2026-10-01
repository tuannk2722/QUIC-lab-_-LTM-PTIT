package bench

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"

	"quic-performance-lab/internal/config"
	"quic-performance-lab/internal/metrics"
)

func scheduleFixture(t *testing.T) Schedule {
	t.Helper()
	w, err := config.LoadWorkloads("../../configs/workloads.json")
	if err != nil {
		t.Fatal(err)
	}
	c, err := config.LoadScenarios("../../configs/scenarios.json")
	if err != nil {
		t.Fatal(err)
	}
	h, err := HashFile("../../configs/workloads.json")
	if err != nil {
		t.Fatal(err)
	}
	g, err := HashFile("../../configs/scenarios.json")
	if err != nil {
		t.Fatal(err)
	}
	return Schedule{SchemaVersion: 1, ExperimentID: "unit_plan", CreatedUTC: time.Now().UTC().Format(time.RFC3339Nano), Suite: "bulk", Profile: "bulk",
		ScenarioNames: []string{"baseline", "rtt50-loss0", "rtt50-loss1", "rtt50-loss3"}, Runs: 30, Warmups: 2, Seed: c.BaseSeed,
		Execution: "ingress-ifb", Addr: "10.10.0.2:4433", ServerName: "10.10.0.2", TimeoutNS: int64(time.Minute),
		Workloads: w, Scenarios: c, WorkloadsSHA256: h, ScenariosSHA256: g, CASHA256: h}
}

func TestScheduleDeterminismBalanceAndBounds(t *testing.T) {
	s := scheduleFixture(t)
	a, err := s.BuildEntries()
	if err != nil {
		t.Fatal(err)
	}
	b, _ := s.BuildEntries()
	if len(a) != 256 || !reflect.DeepEqual(a, b) {
		t.Fatal("default count/determinism")
	}
	seeds := map[uint64]bool{}
	orders := map[string]map[string]int{}
	measured, warmup := 0, 0
	for i := 0; i < len(a); i += 2 {
		x, y := a[i], a[i+1]
		if x.PairID != y.PairID || x.Transport == y.Transport || x.OrderIndex != 0 || y.OrderIndex != 1 || *x.NetemSeed != *y.NetemSeed || seeds[*x.NetemSeed] {
			t.Fatal("pair seed/order")
		}
		seeds[*x.NetemSeed] = true
		key := x.Scenario + "/" + x.Phase
		if orders[key] == nil {
			orders[key] = map[string]int{}
		}
		orders[key][x.Transport]++
		if x.Phase == "measured" {
			measured += 2
		} else {
			warmup += 2
		}
	}
	if measured != 240 || warmup != 16 {
		t.Fatal("phase counts")
	}
	for _, o := range orders {
		if o["tcp"] != o["quic"] {
			t.Fatal("AB/BA not balanced")
		}
	}
	s.Seed++
	c, _ := s.BuildEntries()
	if reflect.DeepEqual(a, c) {
		t.Fatal("seed does not change plan")
	}
	s.SeedDisabled = true
	d, _ := s.BuildEntries()
	for _, e := range d {
		if e.NetemSeed != nil {
			t.Fatal("seed-none ignored")
		}
	}
	s.Runs = 100000
	if _, err := s.BuildEntries(); err == nil {
		t.Fatal("unbounded schedule")
	}
}

func TestImmutableEntryAndNetworkMismatch(t *testing.T) {
	s := scheduleFixture(t)
	s.Runs, s.Warmups = 1, 0
	root := filepath.Join(t.TempDir(), "plan")
	if err := WritePlan(root, s); err != nil {
		t.Fatal(err)
	}
	s, err := LoadSchedule(root)
	if err != nil {
		t.Fatal(err)
	}
	e := s.Entries[0]
	path := filepath.Join(root, "entries", e.RunID+".json")
	if _, _, _, err := LoadEntry(path); err != nil {
		t.Fatal(err)
	}
	n := config.NetworkState{NetworkProfile: "ingress-ifb", Scenario: e.Scenario, ConfigSHA256: s.ScenariosSHA256, NetemSeed: e.NetemSeed,
		MTU: 1500, QueueLimitPackets: 1000, RateMbps: 20}
	if err := MatchNetwork(s, e, n); err != nil {
		t.Fatal(err)
	}
	n.RateMbps = 21
	if err := MatchNetwork(s, e, n); err == nil {
		t.Fatal("wrong applied rate accepted")
	}
	h, _ := HashFile(filepath.Join(root, "schedule.json"))
	e.OrderIndex = 1 - e.OrderIndex
	if err := os.Remove(path); err != nil {
		t.Fatal(err)
	}
	if err := WriteJSON(path, EntryFile{1, h, e}); err != nil {
		t.Fatal(err)
	}
	if _, _, _, err := LoadEntry(path); err == nil {
		t.Fatal("modified entry accepted")
	}
	if err := WritePlan(root, s); err == nil {
		t.Fatal("overwritten plan")
	}
}

func TestMergeMissingInterruptedAndIncomplete(t *testing.T) {
	s := scheduleFixture(t)
	s.Runs, s.Warmups = 1, 0
	s.ScenarioNames = []string{"baseline"}
	s.Execution = "loopback-test"
	root := filepath.Join(t.TempDir(), "plan")
	if err := WritePlan(root, s); err != nil {
		t.Fatal(err)
	}
	s, _ = LoadSchedule(root)
	e := s.Entries[0]
	record := Missing(s, e, "cancelled", "unit cancelled representation", s.CreatedUTC)
	shard := filepath.Join(root, "shards", e.RunID)
	if err := metrics.WriteTrial(shard, record); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(shard, "INCOMPLETE"), []byte("test write failure"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := WriteJSON(filepath.Join(root, "logs", e.RunID+".invocation.json"), Invocation{SchemaVersion: 1, RunID: e.RunID, StartedUTC: s.CreatedUTC}); err != nil {
		t.Fatal(err)
	}
	c, err := Merge(root)
	if err != nil || c.Attempted != 2 || c.Invoked != 1 || c.Missing != 1 || c.Failed != 2 || c.Success != 0 {
		t.Fatalf("counts %+v %v", c, err)
	}
	var first, missing metrics.TrialRecord
	if err := config.DecodeJSON(filepath.Join(root, "raw", e.RunID+".json"), &first, config.MaxConfigBytes); err != nil {
		t.Fatal(err)
	}
	if first.Run.ErrorCode != "result_write_error" || len(first.Streams) != 6 {
		t.Fatal("incomplete output hidden")
	}
	if err := config.DecodeJSON(filepath.Join(root, "raw", s.Entries[1].RunID+".json"), &missing, config.MaxConfigBytes); err != nil {
		t.Fatal(err)
	}
	if missing.Run.ErrorCode != "not_started" || missing.Run.TotalMS != nil || missing.Run.ElapsedMS != 0 || len(missing.Streams) != 6 || missing.Streams[5].ChecksumOK != nil {
		t.Fatal("missing output has fabricated measurements")
	}
	if _, err := Merge(root); err == nil {
		t.Fatal("aggregate overwritten")
	}
}

func TestMergeRejectsUnscheduledOrDifferentCohort(t *testing.T) {
	for _, unknown := range []bool{true, false} {
		s := scheduleFixture(t)
		s.Runs, s.Warmups = 1, 0
		s.ScenarioNames = []string{"baseline"}
		root := filepath.Join(t.TempDir(), "plan")
		if err := WritePlan(root, s); err != nil {
			t.Fatal(err)
		}
		s, _ = LoadSchedule(root)
		e := s.Entries[0]
		if unknown {
			if err := os.Mkdir(filepath.Join(root, "shards", "foreign"), 0700); err != nil {
				t.Fatal(err)
			}
		} else {
			r := Missing(s, e, "timeout", "unit failure", s.CreatedUTC)
			r.Run.ResourceSizeBytes++
			if err := metrics.WriteTrial(filepath.Join(root, "shards", e.RunID), r); err != nil {
				t.Fatal(err)
			}
		}
		if _, err := Merge(root); err == nil {
			t.Fatal("unscheduled/foreign cohort accepted")
		}
	}
}
