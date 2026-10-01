#!/usr/bin/env bash
# P9 privileged orchestration only. Build/dependencies/cert preparation is done
# as the ordinary user. Every file/Go process/check/analysis belongs to that user.
set -euo pipefail
export LC_ALL=C
cd "$(dirname "$0")/.."
repo=$(pwd -P)
source scripts/network/common.sh
source scripts/bench-lifecycle.sh
require_sudo_caller
# Terminal output is best effort; artifact finalization never uses this pipe.
trap '' PIPE
out=
interrupt_case=false
plan_args=()
probe_seed=default
while (( $# )); do
    case "$1" in
        --out=*) out=${1#*=} ;;
        --runs=*|--warmups=*|--seed=*|--scenario=*) plan_args+=("$1") ;;
        --disable-netem-seed) plan_args+=("$1"); probe_seed=none ;;
        --interrupt-case) interrupt_case=true ;;
        *) echo 'Usage: sudo bash scripts/bench.sh [--out=NEW_DIR] [--runs=N --warmups=N --seed=UINT64 --scenario=NAME --disable-netem-seed]' >&2; exit 2 ;;
    esac
    shift
done
run_user() { setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups -- "$@" 8>&-; }
support() { run_user python3 scripts/bench-support.py "$@"; }
say() { printf 'P9: %s\n' "$*" 2>/dev/null || true; }
active=false
server_pid=
trial_pid=
trial_id=
planned=false
merged=false
analyzed=false
forced_stop=false
environment_failed=false
is_running() { [[ -n $1 ]] && kill -0 "$1" 2>/dev/null && [[ $(awk '{print $3}' "/proc/$1/stat" 2>/dev/null) != Z ]]; }
stop_process() {
    local pid=$1 i
    [[ -n $pid ]] || return 0
    forced_stop=false
    kill -TERM "$pid" 2>/dev/null || true
    for ((i=0;i<100;i++)); do is_running "$pid" || break; sleep 0.1; done
    if is_running "$pid"; then forced_stop=true; kill -KILL "$pid"; wait "$pid" || true; return 1; fi
    wait "$pid"
}
host_snapshot() {
    local kind label=$1
    for kind in link address route; do
        if [[ $kind == route ]]; then ip -j route show table all; else ip -j "$kind" show; fi |
            run_user tee "$out/host/$kind.$label.json" >/dev/null
    done
}
host_compare() {
    local kind label=$1
    host_snapshot "$label" || return 1
    for kind in link address route; do cmp -s "$out/host/$kind.before.json" "$out/host/$kind.$label.json" || return 1; done
}
snapshot() { bash scripts/network/inspect.sh | run_user tee "$1" >/dev/null; }
apply() { bash scripts/network/netem.sh --scenario="$1" --profile=ingress-ifb --seed="$2" | run_user tee "$3" >/dev/null; }
infra_fail() { environment_failed=true; echo "P9 environment failure: $*" >&2; exit 3; }
cleanup() {
    local original=$? clean_rc=0 rc
    trap - EXIT
    trap '' INT TERM PIPE
    set +e
    if [[ -n $trial_pid ]]; then
        stop_process "$trial_pid"; rc=$?
        # TERM from our cleanup is expected, while inability to stop is not.
        (( rc == 0 || rc == 130 || rc == 143 || rc == 124 || rc == 1 )) || clean_rc=1
        [[ $forced_stop == false ]] || clean_rc=1
        if [[ -n $trial_id ]]; then support invocation "$out" "$trial_id" "$original" || clean_rc=1; fi
        trial_pid=
    fi
    stop_process "$server_pid" || clean_rc=1
    server_pid=
    if [[ $active == true ]]; then
        bash scripts/network/clear-netem.sh | run_user tee "$out/network/cleanup.json" >/dev/null || clean_rc=1
        bash scripts/network/teardown.sh | run_user tee "$out/logs/teardown.log" >/dev/null || clean_rc=1
        if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER ]]; then clean_rc=1; fi
    fi
    if [[ $planned == true ]]; then
        host_compare final || clean_rc=1
        if [[ $merged == false && ! -e $out/raw ]]; then merge; rc=$?; (( rc <= 1 )) || clean_rc=1; fi
        [[ $merged == true && $analyzed == true ]] || clean_rc=1
        support cleanup "$out" "$original" "$clean_rc" "$environment_failed" || clean_rc=1
        say "results_dir=$out original_exit=$original cleanup_exit=$clean_rc"
    fi
    (( original != 0 || clean_rc == 0 )) || original=1
    exit "$original"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for tool in ip tc ethtool ping python3 setpriv flock sysctl modprobe timeout ss; do command -v "$tool" >/dev/null || lab_die "missing $tool"; done
acquire_experiment_lock
[[ $(uname -r) == *microsoft*WSL2* && $repo == /home/* ]] || lab_die 'Ubuntu WSL2/native Linux /home is required'
[[ $(. /etc/os-release; printf '%s' "$ID") == ubuntu ]] || lab_die 'Ubuntu is required'
[[ -x bin/server && -x bin/bench ]] || lab_die 'run make build as normal user first'
support preflight || lab_die 'G08 prerequisite or pinned analysis dependencies unavailable'
if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER ]]; then lab_die 'stop existing lab server and clean owned topology before benchmark'; fi
run_user test -r certs/server.crt && run_user test -r certs/server.key || lab_die 'make certs as normal user first'
run_user mkdir -p results
if [[ -z $out ]]; then out="$repo/results/$(run_user python3 -c 'import secrets,time; print("p9-bulk-"+time.strftime("%Y%m%dT%H%M%S",time.gmtime())+"-"+secrets.token_hex(4))')"; fi
out=$(realpath -m -- "$out")
if [[ $interrupt_case == true ]]; then plan_args+=(--runs=1 --warmups=0 --scenario=baseline); fi
run_user "$repo/bin/bench" --plan --suite=bulk --profile=bulk --network-profile=ingress-ifb --out="$out" "${plan_args[@]}"
planned=true
host_snapshot before
support runtime "$out"
support list "$out" | run_user tee "$out/schedule.tsv" >/dev/null
say "UTC=$(date -u +%FT%TZ) apps_uid_gid=$SUDO_UID:$SUDO_GID results_dir=$out"
bash scripts/network/setup.sh
active=true
# Actual no-loss RTT checks and neighbor warmup before any performance trial.
for scenario in baseline rtt50-loss0; do
    apply "$scenario" "$probe_seed" "$out/network/$scenario-probe.apply.json" || infra_fail 'probe apply failed'
    for ns in qclient qserver; do
        if [[ $ns == qclient ]]; then dest=10.10.0.2; else dest=10.10.0.1; fi
        bash scripts/run-in-netns.sh "$ns" -- ping -n -c 2 -W 2 "$dest" >/dev/null || infra_fail 'neighbor warmup failed'
        log="$out/probes/$scenario-$ns.log"
        bash scripts/run-in-netns.sh "$ns" -- ping -n -c 12 -i 0.2 -W 2 "$dest" | run_user tee "$log" >/dev/null || infra_fail 'RTT probe failed'
        support probe "$log" "$scenario" "$ns" || infra_fail 'RTT tolerance failed'
    done
done
host_compare active || infra_fail 'host state changed during setup'
ready="$out/ready"
bash scripts/run-in-netns.sh qserver -- /usr/bin/python3 "$repo/scripts/bench-support.py" launch-verified \
    "$out/logs/server.log" "$out" server --transport=both --profile=bulk --listen=10.10.0.2:4433 --ready-file="$ready" 8>&- &
server_pid=$!
for ((i=0;i<100;i++)); do [[ -s $ready ]] && break; is_running "$server_pid" || infra_fail 'server exited before readiness'; sleep 0.1; done
[[ -s $ready && $(stat -c '%u:%g' "/proc/$server_pid") == "$SUDO_UID:$SUDO_GID" ]] || infra_fail 'server readiness/UID failed'
trial_timeout=$(run_user python3 -c 'import json,sys,math; print(math.ceil(json.load(open(sys.argv[1]))["timeout_ns"]/1e9)+15)' "$out/schedule.json")
server_timeout=$(run_user python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["workloads"]["timeouts"]["trial_seconds"]+1)' "$out/schedule.json")
while IFS=$'\t' read -r rid scenario seed; do
    is_running "$server_pid" || infra_fail 'server exited'
    apply "$scenario" "$seed" "$out/network/$rid.apply.json" || infra_fail "apply $rid failed"
    snapshot "$out/network/$rid.before.json" || infra_fail "before inspect $rid failed"
    support invocation "$out" "$rid"
    trial_id=$rid
    say "trial=$rid scenario=$scenario seed=$seed"
    timeout --signal=TERM --kill-after=5s "${trial_timeout}s" bash scripts/run-in-netns.sh qclient -- \
        /usr/bin/python3 "$repo/scripts/bench-support.py" launch-verified "$out/logs/$rid.log" "$out" bench \
        --schedule-entry="$out/entries/$rid.json" --out="$out/shards/$rid" --network-state="$out/network/$rid.before.json" 8>&- &
    trial_pid=$!
    if [[ $interrupt_case == true ]]; then
        sleep 0.2
        contender_rc=0
        bash scripts/bench.sh --out="$out-contender" 8>&- 2>&1 |
            run_user tee "$out/logs/contender.log" >/dev/null || contender_rc=$?
        [[ $contender_rc == 3 && ! -e $out-contender ]] || infra_fail 'competing runner was not refused before planning'
        kill -INT "$$"
    fi
    trial_rc=0
    wait "$trial_pid" || trial_rc=$?
    trial_pid=
    support invocation "$out" "$rid" "$trial_rc"
    trial_id=
    snapshot "$out/network/$rid.after.json" || infra_fail "after inspect $rid failed"
    support network "$out" "$rid" || infra_fail "network validity $rid failed"
    # Input/setup/write errors without a canonical transfer record are infra
    # failures. External watchdog expiry is retained then stops unsafe reset.
    [[ -f $out/shards/$rid/raw/$rid.json && ! -e $out/shards/$rid/INCOMPLETE ]] || infra_fail "missing/incomplete shard $rid (exit $trial_rc)"
    # RunBatch closes its connection before return. On failure allow the
    # server's full deadline to expire before the next reset; then verify
    # drained queues and a quiet path. No probe runs during a transfer.
    if (( trial_rc != 0 )); then sleep "$server_timeout"; fi
    idle_ok=false
    for ((i=0;i<50;i++)); do
        snapshot "$out/network/$rid.idle-$i-before.json" || infra_fail 'idle inspect failed'
        sleep 0.2
        snapshot "$out/network/$rid.idle-$i-after.json" || infra_fail 'idle inspect failed'
        if support idle "$out/network/$rid.idle-$i-before.json" "$out/network/$rid.idle-$i-after.json"; then idle_ok=true; break; fi
    done
    [[ $idle_ok == true ]] || infra_fail 'traffic/queue did not become idle'
done < "$out/schedule.tsv"
stop_process "$server_pid" || infra_fail 'server shutdown failed'
server_pid=
[[ ! -e $ready ]] || infra_fail 'server ready marker remains'
cohort_rc=0
merge || cohort_rc=$?
[[ $merged == true && $analyzed == true ]] || { echo 'P9 merge/analysis failed' >&2; exit 1; }
say "cohort completed; merge_exit=$cohort_rc; cleanup follows"
exit "$cohort_rc"
