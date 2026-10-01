package config

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestNetworkSnapshotRejectsUnverifiedStaleAndWrongNamespace(t *testing.T) {
	seed := uint64(20260928)
	n := NetworkState{SchemaVersion: 1, Verified: true, TimestampUTC: time.Now().UTC().Format(time.RFC3339Nano),
		NetworkProfile: "ingress-ifb", Scenario: "rtt50-loss3", DelayEachWayMS: 25, LossDownstreamPct: 3,
		RateMbps: 20, NetemSeed: &seed, SeedStatus: "requested-and-verified", MTU: 1500, QueueLimitPackets: 1000,
		ConfigSHA256: strings.Repeat("a", 64), ClientNamespaceID: "1:2", ServerNamespaceID: "1:3",
		Observation: json.RawMessage(`{"qclient":{},"qserver":{}}`)}
	b, _ := json.Marshal(n)
	loaded, err := LoadNetworkState(fixture(t, string(b)))
	if err != nil {
		t.Fatal(err)
	}
	if err := loaded.CheckClientNamespace(); err == nil {
		t.Fatal("accepted host namespace for lab snapshot")
	}
	for _, mutate := range []func(*NetworkState){
		func(v *NetworkState) { v.Verified = false },
		func(v *NetworkState) { v.TimestampUTC = time.Now().Add(-6 * time.Minute).Format(time.RFC3339Nano) },
		func(v *NetworkState) { v.TimestampUTC = time.Now().Add(time.Minute).Format(time.RFC3339Nano) },
		func(v *NetworkState) { v.RateMbps = 0 },
		func(v *NetworkState) { v.LossDownstreamPct = 101 },
		func(v *NetworkState) { v.NetemSeed = nil },
		func(v *NetworkState) { v.ClientNamespaceID = v.ServerNamespaceID },
	} {
		bad := n
		mutate(&bad)
		data, _ := json.Marshal(bad)
		if _, err := LoadNetworkState(fixture(t, string(data))); err == nil {
			t.Fatal("invalid snapshot accepted", string(data))
		}
	}
}
