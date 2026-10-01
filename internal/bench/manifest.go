package bench

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"runtime/debug"
	"strings"

	"quic-performance-lab/internal/workload"
)

func command(name string, args ...string) string {
	b, err := exec.Command(name, args...).Output()
	if err != nil {
		return "unknown: command unavailable: " + name
	}
	return string(b)
}
func contents(path string) string {
	b, err := os.ReadFile(path)
	if err != nil {
		return "unknown: unavailable: " + path
	}
	return string(b)
}

// Immutable manifest records facts and paths to per-trial actual observations.
// It distinguishes unknown facts from defaults and from user-reported facts.
func WriteManifest(root string, s Schedule, version string, args []string) error {
	store, err := workload.NewStore(s.Workloads.Profiles[s.Profile], s.Workloads.Limits)
	if err != nil {
		return err
	}
	hashes := map[string]string{}
	for _, path := range []string{"schedule.json"} {
		h, err := HashFile(filepath.Join(root, path))
		if err != nil {
			return err
		}
		hashes[path] = h
	}
	for _, path := range []string{"schemas/result-records.schema.json", "go.mod", "go.sum", "analysis/requirements.txt"} {
		h, err := HashFile(path)
		if err != nil {
			return err
		}
		hashes[path] = h
	}
	buildInfo, _ := debug.ReadBuildInfo()
	sources := map[string]string{}
	for _, dir := range []string{"internal", "cmd", "scripts", "analysis", "configs", "schemas", "tests"} {
		if err := filepath.WalkDir(dir, func(path string, d os.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if d.IsDir() {
				return nil
			}
			ext := filepath.Ext(path)
			if strings.Contains("|.go|.py|.sh|.json|.txt|", "|"+ext+"|") {
				h, err := HashFile(path)
				if err != nil {
					return err
				}
				sources[path] = h
			}
			return nil
		}); err != nil {
			return err
		}
	}
	for _, path := range []string{"AGENTS.md", "Makefile", "go.mod", "go.sum"} {
		h, err := HashFile(path)
		if err != nil {
			return err
		}
		sources[path] = h
	}
	if err := WriteJSON(filepath.Join(root, "source-hashes.json"), sources); err != nil {
		return err
	}
	m := map[string]any{"schema_version": 1, "experiment_id": s.ExperimentID, "created_utc": s.CreatedUTC, "version": version, "cli": args,
		"host_os":            map[string]string{"value": "Windows 11", "source": "user-reported D13; not queried from Linux"},
		"execution_layer":    map[string]string{"requested": "Ubuntu WSL2", "observed_kernel": command("uname", "-r"), "wsl_version": "unknown: Windows WSL CLI not queried"},
		"linux_distribution": contents("/etc/os-release"), "kernel": command("uname", "-a"), "logical_cpu": runtime.NumCPU(), "memory_swap": contents("/proc/meminfo"),
		"go_version": runtime.Version(), "build_info": buildInfo, "build_flags": "Make: -mod=readonly -trimpath; ldflags build revision; GOMAXPROCS=2",
		"git_commit": command("git", "rev-parse", "HEAD"), "git_status": command("git", "status", "--porcelain"), "git_diff_sha256_note": "source file hashes in source-hashes.json; uncommitted source is part of experiment provenance",
		"hashes": hashes, "config_hashes": map[string]string{"workloads": s.WorkloadsSHA256, "scenarios": s.ScenariosSHA256, "ca": s.CASHA256},
		"workload": store.Manifest(), "profile": s.Profile, "trace_mode": "performance", "traces": map[string]bool{"qlog": false, "pcap": false, "keylog": false, "progress": false},
		"tls":             map[string]any{"policy": "TLS1.3 only, explicit CA, ALPN quicbench/1", "actual": "shards/<run_id>/connection.json; absent on setup failure"},
		"tcp_cc":          "network/<run_id>.before.json observation.qclient/qserver.tcp_cc (actual kernel setting); per-socket CC not overridden",
		"quic_cc":         map[string]string{"value": "Reno", "source": "quic-go v0.63.0 internal/ackhandler/sent_packet_handler.go NewCubicSender(..., true // use Reno); docs/VERSIONS.md"},
		"quic_config":     map[string]any{"version": "v1", "initial_stream_credit_bytes": 512 << 10, "max_stream_credit_bytes": 2 << 20, "initial_connection_credit_bytes": 2 << 20, "max_connection_credit_bytes": 16 << 20, "server_max_bidi_streams": 64, "client_incoming_streams": 0, "incoming_uni_streams": 0},
		"socket_buffers":  "client actual getsockopt after timing in connection.json; server actual unknown: not sampled per socket; system defaults in runtime.json",
		"network_profile": s.Execution, "network_placement": "receiver IFB root netem, eth0 ingress flower/mirred; full actual snapshots before/after each trial",
		"mtu": s.Scenarios.MTU, "queue_limit_packets": s.Scenarios.QueueLimitPackets, "offloads": "actual network snapshots offload_preparation and observation",
		"configured_measured_rtt": "schedule scenario delays; measured no-loss probes in probes/*.log.json; loss scenarios not separately pinged during transfer",
		"schedule_seed":           s.Seed, "seed_disabled": s.SeedDisabled, "runner_order": "SplitMix64 v1 seeded starting AB/BA per scenario/phase, alternating pairs; sequential; netem reset after probes and before EVERY trial",
		"timeout_ns": s.TimeoutNS, "failure_policy": "all planned entries represented; transfer failures continue if network verified; infra failure stops; missing/incomplete output fails; original shards retained; elapsed0 for absent observation only",
		"observations": []string{"runtime.json", "network/", "probes/", "logs/", "merge.json", "source-hashes.json", "cleanup.json"},
		"limitations":  []string{"shared WSL2 kernel/CPU; not isolated physical hosts", "TCP kernel/TLS vs quic-go userspace/scheduler/CC differ", "same netem seed is not identical packet loss trace", "downstream includes handshake/control/ACK; drops may include queue overflow", "30 samples per transport/scenario; p95 describes a small sample", "performance dataset alone cannot prove HOL causation; P11 evidence pending"}}
	return WriteJSON(filepath.Join(root, "manifest.json"), m)
}
