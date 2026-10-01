# P8/G08 evidence — PASS, 2026-10-01

User ran `sudo bash tests/system/run.sh --gate G08` at UTC 02:57:20Z. Main gate exit0 and cleanup0; actual results [p8-g08-96nOtS](../../../results/p8-g08-96nOtS/). SIGINT child [p8-g08-qOYl2H](../../../results/p8-g08-qOYl2H/) exited130 as expected, cleanup0. Agent reviewed saved artifacts read-only; did not run this privileged gate or claim human P8 code approval. P9 remains unauthorized.

Source log: [g08-system-rerun.log](g08-system-rerun.log). Review/provenance: [g08-rerun-review.json](g08-rerun-review.json), hashes for 110 artifacts; current status [g08-status.json](g08-status.json). Eight attempted/eight successful/no failed or missing trials, each 6MiB/6 successful hashes (48 total). Four probes have 12 replies each: baseline medians0.320/0.325ms, rtt50-loss0 medians50.500/50.450ms. Agent checked 35 verified kernel snapshots, five cleared snapshots and 15 byte-identical host comparisons. Actual seed20260928 and offloads verified on this kernel/tc version.

| Scenario (20Mbps rate in all) | TCP goodput Mbps | QUIC goodput Mbps | Downstream drops TCP / QUIC |
|---|---:|---:|---:|
| baseline | 19.036 | 18.932 | 0 / 0 |
| rtt50-loss0 | 17.556 | 18.268 | 0 / 0 |
| rtt50-loss1 | 3.054 | 5.558 | 43 / 45 |
| rtt50-loss3 | 1.374 | 2.198 | 112 / 116 |

These are gate evidence observations, one trial per transport/scenario. They do not establish general TCP/QUIC superiority or HOL causality. `measured_trials=0, evidence_trials_excluded=1` means the successful G08 record is deliberately excluded from the P9 main cohort.

Expected negative tests: `Illegal "limit"`/apply exit3 is the injected genuine tc parser failure after partial apply; subsequent error-cleared/after-error snapshots PASS. Child `original_exit=130` is deliberate SIGINT; cleanup0 and unchanged host state confirm interrupt handling. Main final `original_exit=0 cleanup_exit=0` and `g08_exit=0` establish full gate success.

History retained: agent attempts blocked at sudo authentication; actual first user run results/p8-g08-Dw8rGB failed before probes/trials because default IFB fq_codel root0 was mistaken for foreign state. First-fail log/provenance remain unchanged. The baseline fix permits only root0 noqueue or IFB-only root0 fq_codel in owned namespaces, keeps defaults through clear, and rejects other handles/placement.

| Check | Actual result | Evidence |
|---|---|---|
| make build | exit0, Go 1.27.1, three binaries, UID1000 | g08-build.log |
| make test outside sandbox, UID1000 | exit0, config/CLI/metrics and transport/integration regressions | g08-go-suite.log |
| make test-race outside sandbox, UID1000 | exit0, app race suite | g08-race.log |
| make test-network (initial) | exit0, 8 negative tests: units/direction/seed, strict config, foreign state refusal, partial tc failure, offload fixed-ON, RTT short/loss/double-delay rejection, INT rollback | g08-python-tests.log |
| bash syntax, Python compile, gofmt, diff hygiene | exit0, no format output | g08-static.log |
| make -n netem clear-netem inspect-network test-network | exit0; recipes only | g08-make-dry-run.log |
| runner and apply/clear/inspect without root | each exit3, no mutation | g08-nonroot.log, g08-{netem,clear-netem,inspect}-nonroot.log |
| G06 CLI regression, UID1000 outside sandbox | exit0: TCP/QUIC success, TLS failure retained, validators/negative mutations PASS | g08-g06-regression.log; real result path `results/p6-g06-YZJE5Q/` |
| sudo -n bash tests/system/run.sh --gate G08 | attempt exit1 before runner: interactive authentication required | g08-system-attempt.log |
| G08 actual IFB/RTT/rate/counters/seed/offloads and cleanup | PASS; main exit0/cleanup0, expected child130/cleanup0 | g08-system-rerun.log; g08-rerun-review.json; results/p8-g08-96nOtS/ and p8-g08-qOYl2H/ |

| Default IFB baseline regression | PASS, 9 tests including repeated clear and foreign-state refusal | g08-default-qdisc-tests.log |


## Main flow

1. P7 setup creates owned qclient/qserver, eth0 veth and ifb0. Only network wrappers use root; server/client use the original sudo caller UID/GID.
2. Apply reads bounded/strict `configs/scenarios.json`, validates selection/seed, clears old impairment and disables relevant mutable offloads on both namespaces' eth0/ifb0. Fixed/absent/failed actions and before/after are recorded. Any relevant offload remaining ON blocks verification.
3. ingress-ifb attaches netem to receiver ifb0; exact lab IPv4 source/destination flower filters redirect eth0 ingress by mirred egress redirect. qclient IFB receives downstream, qserver IFB receives upstream. ARP bypasses. egress-demo uses eth0 root netem and a separate label. Reserved handles: netem1:, ingressffff:, flower pref10; foreign state is refused.
4. Inspect checks actual kernel qdisc options/placement, filter/destination, offload state, seed and namespace identity before verified=true. Full tc JSON/text/counters, links/addresses and TCP CC accompany metadata. Output is stdout; files are written by user tee/redirect. Root state is under /run/quic-performance-lab and shared ownership lock.
5. Client --network-state requires recent<=5min snapshot and matching qclient identity, copies configured/verified fields into v1 raw/CSV on success and failure, phase=evidence/trace_mode=evidence. It does not query tc or lock kernel state through the transfer. No flag keeps loopback-test/exploratory. Wrapper must verify before/after and reset after probes while idle.
6. Apply errors/INT/TERM roll back shaping and return nonzero; clear removes qdisc/filter/state but leaves namespace and offloads OFF until teardown. Teardown removes owned topology/state. SIGKILL cannot run traps.

## Full G08 command — interactive Ubuntu WSL2

From the native Linux repo root, first stop any lab foreground server with Ctrl+C and clear/teardown owned topology if it exists. The runner refuses existing names/marker and will not delete foreign resources. Build and certificate generation stay unprivileged.

```bash
make build
make test-network
test -r certs/server.crt && test -r certs/server.key || make certs
mkdir -p results docs/evidence/p8
set -o pipefail
sudo bash tests/system/run.sh --gate G08 2>&1 | tee docs/evidence/p8/g08-system-review.log
g08_status=${PIPESTATUS[0]}; printf 'g08_exit=%s\n' "$g08_status" | tee -a docs/evidence/p8/g08-system-review.log
```

Enter sudo authentication in your terminal. The runner prints `results_dir=.../results/p8-g08-*`. It keeps probes/network/kernel/host snapshots and all attempted trial raw/CSV, with `gate-summary.json` showing represented success/failure counts, missing records, original/cleanup status and checks. Interrupted child case has its own result dir. The main result directory contains:

- `probes/baseline-{qclient,qserver}.log[.json]`, `probes/rtt50-loss0-{qclient,qserver}.log[.json]`: 12 ping replies each direction; baseline median<10ms; rtt50 median40..60ms, zero loss.
- `network/*.apply.json`, `*.before.json`, `*.after.json`, `*.check.json`: actual kernel/offload/seed/counter state and checks; reset per transport after probes. Root netem and redirect counters must increase in both directions, downstream bytes dominate bulk; loss bulk must show observed downstream drops, without claiming every drop is random-loss or DATA-only.
- Eight actual trial dirs: TCP/QUIC ×baseline/rtt50-loss0/1/3. Each has raw/runs/streams and all six checksums. Sustained transfer>=1s and 0<goodput<=110% configured20Mbps; no numeric QUIC superiority criterion. Failures remain in records and gate summary; infra error stops the gate.
- Profile transitions ingress→egress-demo→ingress, repeated clear, genuine tc parser error after qclient apply (`QUICLAB_FAIL_NETEM_AFTER=client` is gate-only), then rollback/clear/teardown. Final child SIGINT must exit130 with no namespace/process/marker left; host link/address/route snapshots remain identical.

Only mark G08 PASS after the full gate exits0, all checks and raw evidence are reviewed, and the verified receiver path remains valid. Keep the attempt log; capture reruns to a new log if necessary. If the gate fails, inspect cleanup/error output before any retry. `make clear-netem` leaves namespaces; stop managed server before `make clean-network`. No unrelated PID is killed.

Seed defaults to config base_seed. Requested seed not reported/supported by kernel/tc makes apply fail; no silent fallback. After diagnosing lack of support, an explicit no-seed run is supported:

```bash
sudo env NETEM_SEED=none bash tests/system/run.sh --gate G08
```

This records netem_seed=null and seed_status=disabled-explicitly, a reproducibility limitation; save its log separately. Do not use no-seed to mask another tc error. Same configured seed never means identical TCP/QUIC loss traces.

## Files changed

- New: `scripts/network/{netem,clear-netem,inspect}.sh`, `scripts/network/state.py`; `internal/config/network.go`, `network_test.go`; `tests/system/{g08.sh,check_g08.py,test_network.py}`; `docs/evidence/p8/` and `docs/evidence/p7/g07-rerun-review.json`.
- Updated: `Makefile`, `scripts/network/teardown.sh`, `tests/system/run.sh`; `internal/cli/{cli,cli_test}.go`, `internal/metrics/{result,result_test}.go`; `.codex/TASK.md`, `README.md`, `START_HERE.md`; `docs/{00-INDEX,IMPLEMENTATION_PLAN,NETWORK_AND_BENCHMARK,CLI_CONTRACT,METRICS_AND_RESULTS,CONTEXT_AND_DECISIONS,ACCEPTANCE_RESULTS,AI_USAGE}.md`, `docs/evidence/p7/README.md`.
- No config numbers, result schema, transport protocol, pinned dependencies or original references changed. No commit, benchmark cohort, plot, PCAP/qlog or 0-RTT implementation.

## Review focus and limits

Review receiver placement/lab IPv4 match and no duplicate shaping; actual tc JSON units (seconds, loss fraction, rate bytes/s); seed checks; offload fixed/absent semantics; partial-failure/signal cleanup and ownership; snapshot freshness/identity and failed-row metadata. Sources reviewed: [netem manual](https://man7.org/linux/man-pages/man8/tc-netem.8.html), [upstream q_netem](https://github.com/iproute2/iproute2/blob/main/tc/q_netem.c), [mirred](https://github.com/iproute2/iproute2/blob/main/tc/m_mirred.c), [JSON rate](https://github.com/iproute2/iproute2/blob/main/lib/json_print.c). The successful actual G08 rerun verified parser/offload/seed behavior for the recorded kernel and tc version.

Current actual G08 is PASS. The recorded RTT/rate/counters are gate evidence; no main cohort is authorized and no general loss/HOL performance conclusion is supported. Snapshot metadata is not a continuous guarantee against another operator changing qdiscs. G07 first-load IFB path after a fresh boot remains untested. This is agent self-review; human P8 review has not occurred.
