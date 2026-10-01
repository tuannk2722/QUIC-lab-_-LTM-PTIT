#!/usr/bin/env bash
# Real G08 only; build/certs as normal user before sudo. No benchmark P9.
set -euo pipefail
export LC_ALL=C
gate_seed=${NETEM_SEED:-default}
cd "$(dirname "$0")/../.."
repo=$(pwd -P)
source scripts/network/common.sh
require_sudo_caller
interrupt_case=false
if [[ $# -gt 0 ]]; then
    [[ $# == 1 && $1 == --interrupt-case ]] || { echo 'invalid G08 argument' >&2; exit 2; }
    interrupt_case=true
fi
case_dir=
server_pid=
topology_active=false
fail() { echo "G08 FAIL: $*" >&2; exit 1; }
say() { echo "G08: $*"; }
run_user() { setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups -- "$@"; }
running() {
    [[ -n $server_pid ]] && kill -0 "$server_pid" 2>/dev/null &&
        [[ $(awk '{print $3}' "/proc/$server_pid/stat" 2>/dev/null) != Z ]]
}
stop_server() {
    local i rc=0
    [[ -n $server_pid ]] || return 0
    kill -TERM "$server_pid" 2>/dev/null || true
    for ((i=0; i<100; i++)); do running || break; sleep 0.1; done
    if running; then kill -KILL "$server_pid"; rc=1; fi
    wait "$server_pid" || rc=1
    server_pid=
    return "$rc"
}
host_snapshot() {
    local label=$1 kind
    for kind in link address route; do
        if [[ $kind == route ]]; then
            ip -j route show table all | run_user tee "$case_dir/host/$kind.$label.json" >/dev/null
        else
            ip -j "$kind" show | run_user tee "$case_dir/host/$kind.$label.json" >/dev/null
        fi
    done
}
host_compare() {
    local label=$1 kind
    host_snapshot "$label" || return 1
    for kind in link address route; do
        if ! cmp -s "$case_dir/host/$kind.before.json" "$case_dir/host/$kind.$label.json"; then
            echo "G08: host $kind changed ($label)" >&2
            return 1
        fi
    done
    say "host link/address/route unchanged at $label"
}
absent() {
    ! namespace_exists qclient && ! namespace_exists qserver && [[ ! -e $LAB_MARKER ]] &&
        [[ ! -e $LAB_STATE_DIR/impairment-v1.json ]] || fail 'namespace or marker remains'
}
cleanup() {
    local rc=$? cleanup_rc=0
    trap - EXIT INT TERM
    stop_server || cleanup_rc=1
    if [[ $topology_active == true ]]; then
        bash scripts/network/clear-netem.sh | run_user tee "$case_dir/network/cleanup.json" >/dev/null || cleanup_rc=1
        bash scripts/network/teardown.sh || cleanup_rc=1
    fi
    if [[ -n $case_dir ]]; then
        host_compare final || cleanup_rc=1
        if ! run_user python3 - "$case_dir" "$rc" "$cleanup_rc" <<'PY'
import csv, json, sys
from pathlib import Path
root = Path(sys.argv[1])
rc, cleanup_rc = map(int, sys.argv[2:])
trials = []
for path in sorted(root.glob('*/runs.csv')):
    with path.open(newline='') as f:
        trials.extend(dict(row, result_path=str(path.parent)) for row in csv.DictReader(f))
attempt_file = root/'attempted-runs.txt'
attempted = attempt_file.read_text().splitlines() if attempt_file.exists() else []
represented = {r['run_id'] for r in trials}
summary = {'gate': 'G08', 'status': 'PASS' if rc == cleanup_rc == 0 else 'INTERRUPTED' if rc in (130,143) else 'FAIL',
           'original_exit': rc, 'cleanup_exit': cleanup_rc,
           'attempted_invocations': len(attempted), 'trial_rows': len(trials),
           'n_success': sum(r['success']=='true' for r in trials), 'n_failed': sum(r['success']=='false' for r in trials),
           'missing_trial_records': [rid for rid in attempted if rid not in represented], 'trials': trials,
           'probes': [json.loads(p.read_text()) for p in sorted((root/'probes').glob('*.log.json'))],
           'traffic_checks': [json.loads(p.read_text()) for p in sorted((root/'network').glob('*.check.json'))]}
(root/'gate-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
PY
        then cleanup_rc=1; fi
        say "results_dir=$case_dir original_exit=$rc cleanup_exit=$cleanup_rc"
    fi
    (( rc != 0 || cleanup_rc == 0 )) || rc=1
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for tool in ip tc ethtool ping python3 setpriv flock sysctl modprobe; do
    command -v "$tool" >/dev/null || lab_die "missing $tool"
done
[[ -x bin/server && -x bin/client ]] || lab_die 'make build as normal user first'
run_user test -r certs/server.crt && run_user test -r certs/server.key || lab_die 'make certs as normal user first'
[[ $(uname -r) == *microsoft*WSL2* ]] || lab_die 'real gate requires Ubuntu WSL2 per D13'
[[ $repo == /home/* ]] || lab_die 'run from native Linux /home repo'
if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER ]]; then
    lab_die 'existing lab topology; stop server and clean owned topology before G08'
fi
run_user mkdir -p results
case_dir=$(run_user mktemp -d "$repo/results/p8-g08-XXXXXX")
run_user mkdir "$case_dir/host" "$case_dir/network" "$case_dir/probes"
host_snapshot before
say "UTC=$(date -u +%FT%TZ) app_uid_gid=$SUDO_UID:$SUDO_GID results_dir=$case_dir"
uname -a | run_user tee "$case_dir/kernel.txt"
tc -V | run_user tee "$case_dir/tc-version.txt"
bash scripts/network/setup.sh
topology_active=true
snapshot() { bash scripts/network/inspect.sh | run_user tee "$1" >/dev/null; }
apply() {
    local scenario=$1 profile=$2 label=$3
    bash scripts/network/netem.sh --scenario="$scenario" --profile="$profile" \
        --seed="$gate_seed" | run_user tee "$case_dir/network/$label.apply.json" >/dev/null
}
check_clear() {
    bash scripts/network/clear-netem.sh | run_user tee "$case_dir/network/$1.clear.json" >/dev/null
    run_user python3 tests/system/check_g08.py cleared "$case_dir/network/$1.clear.json"
}
if [[ $interrupt_case == true ]]; then
    apply baseline ingress-ifb interrupt
    kill -INT "$$"
    exit 1 # trap must exit 130; reaching this is a test failure.
fi

# Warm neighbor resolution before measurements; no background probe in trials.
for ns in qclient qserver; do
    if [[ $ns == qclient ]]; then dest=10.10.0.2; else dest=10.10.0.1; fi
    bash scripts/run-in-netns.sh "$ns" -- ping -n -c 2 -W 2 "$dest" >/dev/null
done
for scenario in baseline rtt50-loss0; do
    apply "$scenario" ingress-ifb "$scenario-probe"
    snapshot "$case_dir/network/$scenario-probe.before.json"
    for ns in qclient qserver; do
        if [[ $ns == qclient ]]; then dest=10.10.0.2; else dest=10.10.0.1; fi
        log="$case_dir/probes/$scenario-$ns.log"
        bash scripts/run-in-netns.sh "$ns" -- ping -n -c 12 -i 0.2 -W 2 "$dest" | run_user tee "$log"
        run_user python3 tests/system/check_g08.py probe "$log" "$scenario" "$ns"
    done
    snapshot "$case_dir/network/$scenario-probe.after.json"
done
host_compare active

ready="$case_dir/ready"
bash scripts/run-in-netns.sh qserver -- "$repo/bin/server" --transport=both --profile=bulk \
    --listen=10.10.0.2:4433 --ready-file="$ready" &
server_pid=$!
for ((i=0; i<100; i++)); do [[ -s $ready ]] && break; running || fail 'server exited'; sleep 0.1; done
[[ -s $ready ]] || fail 'server readiness timeout'
[[ $(stat -c '%u:%g' "/proc/$server_pid") == "$SUDO_UID:$SUDO_GID" ]] || fail 'server not unprivileged'

# Reset after probes and before each transport; same configured seed is not
# an identical packet-loss trace for TCP/QUIC. All four main config scenarios.
for scenario in baseline rtt50-loss0 rtt50-loss1 rtt50-loss3; do
    for transport in tcp quic; do
        label="$scenario-$transport"
        apply "$scenario" ingress-ifb "$label"
        before="$case_dir/network/$label.before.json"
        after="$case_dir/network/$label.after.json"
        snapshot "$before"
        output="$case_dir/$label"
        say "trial=$label seed=$gate_seed network_profile=ingress-ifb"
        printf '%s\n' "$label" | run_user tee -a "$case_dir/attempted-runs.txt" >/dev/null
        trial_rc=0
        bash scripts/run-in-netns.sh qclient -- "$repo/bin/client" --transport="$transport" \
            --mode=cold --profile=bulk --addr=10.10.0.2:4433 --server-name=10.10.0.2 \
            --ca="$repo/certs/server.crt" --format=json --network-state="$before" \
            --experiment-id=p8_g08 --run-id="$label" --out="$output" || trial_rc=$?
        snapshot "$after"
        run_user python3 analysis/validate.py "$output"
        (( trial_rc == 0 )) || fail "trial $label exit $trial_rc; failed records retained"
        run_user python3 tests/system/check_g08.py transfer "$before" "$after" "$output"
    done
done
stop_server || fail 'managed server did not stop cleanly'
[[ ! -e $ready ]] || fail 'server readiness marker remains'

# Profile switch in both directions; inspect validates no duplicate shaping.
apply rtt50-loss3 egress-demo egress-demo
snapshot "$case_dir/network/egress-demo.inspect.json"
apply rtt50-loss0 ingress-ifb ingress-again
snapshot "$case_dir/network/ingress-again.inspect.json"
check_clear explicit
check_clear idempotent

# Actual tc error after partially applying, not just an invalid config input.
if QUICLAB_FAIL_NETEM_AFTER=client bash scripts/network/netem.sh --scenario=rtt50-loss0 --seed="$gate_seed" \
    2>&1 | run_user tee "$case_dir/network/error-apply.log"; then
    fail 'injected netem parser error unexpectedly succeeded'
else
    say "injected netem apply exit=$? (expected nonzero)"
fi
snapshot "$case_dir/network/error-cleared.json"
run_user python3 tests/system/check_g08.py cleared "$case_dir/network/error-cleared.json"
check_clear after-error
bash scripts/network/teardown.sh
topology_active=false
absent
host_compare teardown

# Runner SIGINT must preserve 130 while clearing impairment and topology.
interrupt_rc=0
bash tests/system/g08.sh --interrupt-case || interrupt_rc=$?
[[ $interrupt_rc == 130 ]] || fail "interrupt cleanup exit=$interrupt_rc, expected 130"
absent
host_compare interrupt
say 'PASS: G08 receiver IFB path, RTT, counters/direction, seed/offloads, TCP+QUIC rate/loss, profile switch, tc-error and SIGINT cleanup'
