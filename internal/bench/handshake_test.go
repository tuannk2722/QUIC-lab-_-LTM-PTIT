package bench

import "testing"

func TestHandshakePlanCountsOrderSeedAndBounds(t *testing.T) {
	s := scheduleFixture(t)
	s.Suite = "handshake"
	s.Profile = "handshake"
	s.ScenarioNames = []string{"rtt50-loss0"}
	entries, err := s.BuildEntries()
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 96 {
		t.Fatalf("count=%d", len(entries))
	}
	positions := map[string][3]int{}
	measured, warm := 0, 0
	for i := 0; i < len(entries); i += 3 {
		group := entries[i : i+3]
		for j, e := range group {
			if e.Transport != "quic" || e.OrderIndex != j || e.PairID != group[0].PairID || *e.NetemSeed != *group[0].NetemSeed {
				t.Fatal("invalid mode triple")
			}
			if e.Phase == "measured" {
				measured++
				v := positions[e.Mode]
				v[j]++
				positions[e.Mode] = v
			} else {
				warm++
			}
		}
		if i >= 3 && *entries[i-3].NetemSeed == *group[0].NetemSeed {
			t.Fatal("seed reused")
		}
	}
	if measured != 90 || warm != 6 {
		t.Fatalf("counts %d %d", measured, warm)
	}
	for _, mode := range []string{"cold", "resumed", "early"} {
		if positions[mode] != [3]int{10, 10, 10} {
			t.Fatalf("mode order unbalanced %+v", positions)
		}
	}
	s.Profile = "bulk"
	if _, err := s.BuildEntries(); err == nil {
		t.Fatal("bulk mixed into handshake")
	}
	s.Profile = "handshake"
	s.ScenarioNames = []string{"baseline"}
	if _, err := s.BuildEntries(); err == nil {
		t.Fatal("wrong network accepted")
	}
}
