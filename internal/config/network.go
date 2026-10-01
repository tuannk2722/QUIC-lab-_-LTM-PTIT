package config

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"regexp"
	"syscall"
	"time"
)

// NetworkState is a recent inspect.sh snapshot. The privileged orchestrator
// verifies actual kernel settings; this reader does not call tc or claim G08.
type NetworkState struct {
	SchemaVersion      int             `json:"schema_version"`
	Verified           bool            `json:"verified"`
	TimestampUTC       string          `json:"timestamp_utc"`
	NetworkProfile     string          `json:"network_profile"`
	Scenario           string          `json:"scenario"`
	DelayEachWayMS     float64         `json:"delay_each_way_ms"`
	LossDownstreamPct  float64         `json:"loss_downstream_pct"`
	LossUpstreamPct    float64         `json:"loss_upstream_pct"`
	RateMbps           float64         `json:"rate_mbps"`
	NetemSeed          *uint64         `json:"netem_seed"`
	SeedStatus         string          `json:"seed_status"`
	QueueLimitPackets  int             `json:"queue_limit_packets"`
	MTU                int             `json:"mtu"`
	ConfigSHA256       string          `json:"config_sha256"`
	ClientNamespaceID  string          `json:"client_namespace_id"`
	ServerNamespaceID  string          `json:"server_namespace_id"`
	OffloadPreparation json.RawMessage `json:"offload_preparation"`
	Observation        json.RawMessage `json:"observation"`
}

func LoadNetworkState(path string) (NetworkState, error) {
	var n NetworkState
	if err := decode(path, &n); err != nil {
		return n, err
	}
	if n.SchemaVersion != 1 || !n.Verified || (n.NetworkProfile != "ingress-ifb" && n.NetworkProfile != "egress-demo") || n.Scenario == "" || n.MTU != 1500 || n.QueueLimitPackets < 1 || n.QueueLimitPackets > 1000000 || len(n.Observation) < 3 || string(n.Observation) == "null" {
		return n, fmt.Errorf("unverified or invalid network state")
	}
	if !regexp.MustCompile(`^[a-f0-9]{64}$`).MatchString(n.ConfigSHA256) || !regexp.MustCompile(`^[0-9]+:[0-9]+$`).MatchString(n.ClientNamespaceID) || !regexp.MustCompile(`^[0-9]+:[0-9]+$`).MatchString(n.ServerNamespaceID) || n.ClientNamespaceID == n.ServerNamespaceID {
		return n, fmt.Errorf("invalid config hash or namespace identities")
	}
	for _, v := range []float64{n.DelayEachWayMS, n.LossDownstreamPct, n.LossUpstreamPct, n.RateMbps} {
		if math.IsNaN(v) || math.IsInf(v, 0) {
			return n, fmt.Errorf("nonfinite network value")
		}
	}
	if n.DelayEachWayMS < 0 || n.DelayEachWayMS > 3600000 || n.LossDownstreamPct < 0 || n.LossDownstreamPct > 100 || n.LossUpstreamPct < 0 || n.LossUpstreamPct > 100 || n.RateMbps <= 0 || n.RateMbps > 1000000 {
		return n, fmt.Errorf("network values out of bounds")
	}
	if (n.NetemSeed == nil && n.SeedStatus != "disabled-explicitly") || (n.NetemSeed != nil && n.SeedStatus != "requested-and-verified") {
		return n, fmt.Errorf("inconsistent netem seed status")
	}
	ts, err := time.Parse(time.RFC3339Nano, n.TimestampUTC)
	if err != nil || time.Since(ts) > 5*time.Minute || time.Until(ts) > 5*time.Second {
		return n, fmt.Errorf("network snapshot must be recent (within 5 minutes)")
	}
	return n, nil
}

func (n NetworkState) CheckClientNamespace() error {
	info, err := os.Stat("/proc/self/ns/net")
	if err != nil {
		return err
	}
	st, ok := info.Sys().(*syscall.Stat_t)
	if !ok || fmt.Sprintf("%d:%d", st.Dev, st.Ino) != n.ClientNamespaceID {
		return fmt.Errorf("client is not in the qclient namespace of this snapshot")
	}
	return nil
}
