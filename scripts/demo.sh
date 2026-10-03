#!/usr/bin/env bash
# P12 managed, offline-ready live samples. Apps and file helpers remain non-root.
set -euo pipefail
export LC_ALL=C
unset QLOGDIR
trap '' PIPE
cd "$(dirname "$0")/.."
repo=$(pwd -P)
usage() { echo 'Usage: sudo bash scripts/demo.sh basic|baseline|loss|0rtt [--out=ABS_NEW_DIR] [--backup=ABS_ACCEPTED_G11_ROOT]' >&2; }
[[ $# -ge 1 ]] || { usage; exit 2; }
kind=$1; shift
case "$kind" in basic|baseline|loss|0rtt) ;; *) usage; exit 2;; esac
out= backup=
for arg in "$@"; do
 case "$arg" in
  --out=*) [[ -z $out ]] || { usage; exit 2; }; out=${arg#*=}; [[ -n $out ]] || exit 2;;
  --backup=*) [[ -z $backup ]] || { usage; exit 2; }; backup=${arg#*=}; [[ -n $backup ]] || exit 2;;
  *) usage; exit 2;;
 esac
done
[[ -z $out || $out == /* ]] && [[ -z $backup || $backup == /* ]] || { usage; exit 2; }
[[ ${NETEM_SEED:-default} == default || ${NETEM_SEED:-default} == none ]] || { echo 'Demo accepts NETEM_SEED=default|none' >&2; exit 2; }
source scripts/network/common.sh
source scripts/process-lifecycle.sh
require_sudo_caller
for tool in ip tc ethtool ping python3 sysctl setpriv flock modprobe tcpdump rg timeout; do command -v "$tool" >/dev/null || lab_die "missing $tool"; done
acquire_experiment_lock
[[ $(uname -r) == *microsoft*WSL2* && $repo == /home/* && $(. /etc/os-release; printf '%s' "$ID") == ubuntu ]] || lab_die 'Ubuntu WSL2/native /home required'
run_user() { setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups --reset-env -- env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C "NETEM_SEED=${NETEM_SEED:-default}" "$@" 8>&-; }
support() { run_user python3 scripts/demo-support.py "$@"; }
# Accept only a complete, idle topology belonging to this caller. Refuse every
# existing PID, even a foreground lab server, rather than infer PID ownership.
reused=false
if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER || -L $LAB_MARKER ]]; then
 require_owned_topology
 for ns in qclient qserver; do
  pids=$(ip netns pids "$ns")
  [[ -z $pids ]] || lab_die "$ns has active processes ($pids); stop the foreground server before demo"
 done
 reused=true
fi
run_user python3 scripts/bench-support.py preflight
run_user bash -c 'for tool in ip tc ethtool ping python3 sysctl setpriv rg; do command -v "$tool" >/dev/null || { printf "Demo: owner PATH missing %s\n" "$tool" >&2; exit 3; }; done'
run_user bash scripts/tshark.sh -v >/dev/null
run_user mkdir -p results
if [[ -z $out ]]; then out="$repo/results/p12-demo-$kind-$(run_user python3 -c 'import secrets;print(secrets.token_hex(6))')"; fi
root=$(realpath -m -- "$out")
[[ ! -e $root && ! -L $root && -d $(dirname "$root") ]] || lab_die 'demo output must be a new directory with existing parent'
[[ $(basename "$root") =~ ^[A-Za-z0-9_-]{1,128}$ ]] || { echo 'Demo directory basename must be a valid experiment_id (1..128 ASCII letters/digits/_/-)' >&2; exit 2; }
if [[ -n $backup ]]; then backup=$(realpath -e -- "$backup"); fi
support prepare "$root" "$kind" "$backup"
active=$reused server_pid= client_pid= client_cap= server_cap= ready=
host_snapshot() {
 local label=$1 field
 for field in link address route; do
  if [[ $field == route ]]; then ip -j route show table all; else ip -j "$field" show; fi |
   run_user tee "$root/host/$field.$label.json" >/dev/null
 done
}
cleanup() {
 local original=$? clean=0 check=0 field
 trap - EXIT; trap '' INT TERM; set +e
 stop_process "$client_pid" true || clean=1
 stop_process "$server_pid" || clean=1
 stop_process "$client_cap" true 400 || clean=1
 stop_process "$server_cap" true 400 || clean=1
 if [[ $active == true ]]; then
  bash scripts/network/clear-netem.sh | run_user tee "$root/network/cleanup.json" >/dev/null || clean=1
  bash scripts/network/teardown.sh > >(run_user python3 scripts/evidence-support.py sink "$root/logs/teardown.log") || clean=1
 fi
 host_snapshot final || clean=1
 for field in link address route; do cmp -s "$root/host/$field.before.json" "$root/host/$field.final.json" || clean=1; done
 if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER || -L $LAB_MARKER ]]; then clean=1; fi
 # Full causal audit runs after qlog/capture/host cleanup; all partial attempts
 # remain visible on interrupted or failed demos. Output survives closed pipes.
 run_user python3 scripts/bench-support.py launch-log "$root/logs/check.log" /usr/bin/python3 "$repo/scripts/demo-support.py" finish "$root" "$original" "$clean" || check=$?
 [[ ! -f $root/logs/check.log ]] || cat "$root/logs/check.log" 2>/dev/null || true
 printf 'Demo %s: results=%s original_exit=%s cleanup_exit=%s audit_exit=%s\n' "$kind" "$root" "$original" "$clean" "$check" 2>/dev/null || true
 if (( original == 0 && (clean != 0 || check != 0) )); then original=1; fi
 exit "$original"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
host_snapshot before
run_user python3 scripts/bench-support.py runtime "$root"
support list "$root" | run_user tee "$root/demo-plan.tsv" >/dev/null
if [[ $reused == false ]]; then bash scripts/network/setup.sh; fi
active=true
host_snapshot active
for field in link address route; do cmp -s "$root/host/$field.before.json" "$root/host/$field.active.json" || lab_die 'host state changed'; done
probe_seed=default; [[ ${NETEM_SEED:-default} != none ]] || probe_seed=none
for scenario in baseline rtt50-loss0; do
 bash scripts/network/netem.sh --scenario="$scenario" --profile=ingress-ifb --seed="$probe_seed" | run_user tee "$root/network/$scenario-probe.json" >/dev/null
 for ns in qclient qserver; do
  dest=10.10.0.2; [[ $ns != qserver ]] || dest=10.10.0.1
  bash scripts/run-in-netns.sh "$ns" -- ping -n -c 2 -W 2 "$dest" >/dev/null
  log="$root/probes/$scenario-$ns.log"
  bash scripts/run-in-netns.sh "$ns" -- ping -n -c 12 -i .2 -W 2 "$dest" | run_user tee "$log" >/dev/null
  run_user python3 scripts/bench-support.py probe "$log" "$scenario" "$ns"
 done
done
profile=bulk; [[ $kind != basic && $kind != 0rtt ]] || profile=handshake
ready="$root/traces/ready"
printf 'Demo %s: %s workload, verified ingress IFB; paired capture and client progress enabled.\n' "$kind" "$profile"
bash scripts/run-in-netns.sh qserver -- /usr/bin/python3 "$repo/scripts/bench-support.py" launch-verified "$root/logs/server.log" "$root" server \
 --transport=both --listen=10.10.0.2:4433 --profile="$profile" --allow-0rtt=true --ready-file="$ready" \
 --qlog-dir="$root/traces/server-qlog" --keylog="$root/traces/server.keylog" 8>&- & server_pid=$!
for ((j=0;j<100;j++)); do [[ -s $ready ]] && break; managed_process_running "$server_pid" || lab_die 'demo server exited'; sleep .05; done
[[ -s $ready && $(stat -c '%u:%g' "/proc/$server_pid") == "$SUDO_UID:$SUDO_GID" ]] || lab_die 'demo server readiness/UID failed'
run_trial() {
 local rid=$1 profile=$2 tr=$3 mode=$4 scenario=$5 seed=$6 rc=0 idle=false
 support run "$root" "$rid" pending
 bash scripts/network/netem.sh --scenario="$scenario" --profile=ingress-ifb --seed="$seed" | run_user tee "$root/network/$rid.apply.json" >/dev/null
 bash scripts/network/inspect.sh | run_user tee "$root/network/$rid.before.json" >/dev/null
 run_user mkdir "$root/traces/$rid" "$root/captures/$rid"
 bash scripts/capture.sh qclient "$root/captures/$rid/qclient" 150 & client_cap=$!
 bash scripts/capture.sh qserver "$root/captures/$rid/qserver" 150 & server_cap=$!
 for ((j=0;j<200;j++)); do [[ -f $root/captures/$rid/qclient/ready && -f $root/captures/$rid/qserver/ready ]] && break; sleep .05; done
 [[ -f $root/captures/$rid/qclient/ready && -f $root/captures/$rid/qserver/ready ]] || lab_die 'paired demo capture not ready'
 timeout --signal=TERM --kill-after=5s 135s bash scripts/run-in-netns.sh qclient -- /usr/bin/python3 "$repo/scripts/bench-support.py" launch-verified \
  "$root/logs/$rid-client.log" "$root" client --transport="$tr" --mode="$mode" --profile="$profile" --addr=10.10.0.2:4433 --server-name=10.10.0.2 \
  --experiment-id="$(basename "$root")" --run-id="$rid" --out="$root/runs/$rid" --network-state="$root/network/$rid.before.json" \
  --qlog-dir="$root/traces/$rid/client-qlog" --keylog="$root/traces/$rid/client.keylog" --progress --format=json 8>&- & client_pid=$!
 wait "$client_pid" || rc=$?; client_pid=
 support run "$root" "$rid" "$rc"
 [[ -f $root/runs/$rid/raw/$rid.json && ! -f $root/runs/$rid/INCOMPLETE && $rc -le 1 ]] || lab_die "incomplete demo trial $rid (exit$rc)"
 # A failed transfer ends this sample before any later network reset. Stop
 # the known server while capture is still active, then retain its full trace.
 if [[ $rc != 0 ]]; then stop_process "$server_pid"; server_pid=; fi
 stop_process "$client_cap" true 400; client_cap=
 stop_process "$server_cap" true 400; server_cap=
 bash scripts/network/inspect.sh | run_user tee "$root/network/$rid.after.json" >/dev/null
 for ((j=0;j<50;j++)); do
  bash scripts/network/inspect.sh | run_user tee "$root/network/$rid.idle-$j-before.json" >/dev/null; sleep .2
  bash scripts/network/inspect.sh | run_user tee "$root/network/$rid.idle-$j-after.json" >/dev/null
  if run_user python3 scripts/bench-support.py idle "$root/network/$rid.idle-$j-before.json" "$root/network/$rid.idle-$j-after.json"; then idle=true; break; fi
 done
 [[ $idle == true ]] || lab_die 'demo traffic not idle before next reset'
 printf 'Demo %s: run=%s transport=%s mode=%s transfer_exit=%s\n' "$kind" "$rid" "$tr" "$mode" "$rc"
 [[ $rc == 0 ]] || exit 1
}
while IFS=$'\t' read -r rid profile tr mode scenario seed; do run_trial "$rid" "$profile" "$tr" "$mode" "$scenario" "$seed"; done < "$root/demo-plan.tsv"
stop_process "$server_pid"; server_pid=
[[ ! -e $ready ]] || lab_die 'demo server ready marker remains'
