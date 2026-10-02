#!/usr/bin/env bash
# P11 actual ingress-IFB evidence gate; instrumentation never enters main data.
set -euo pipefail
export LC_ALL=C
unset QLOGDIR
trap '' PIPE
cd "$(dirname "$0")/../.."
repo=$(pwd -P)
source scripts/network/common.sh
source scripts/process-lifecycle.sh
require_sudo_caller
[[ $# == 0 ]] || { echo 'G11 takes no count overrides' >&2; exit 2; }
for tool in ip tc ethtool ping python3 sysctl setpriv flock modprobe tcpdump rg timeout; do command -v "$tool" >/dev/null || lab_die "missing $tool"; done
acquire_experiment_lock
[[ $(uname -r) == *microsoft*WSL2* && $repo == /home/* && $(. /etc/os-release; printf '%s' "$ID") == ubuntu ]] || lab_die 'Ubuntu WSL2/native /home required'
if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER ]]; then lab_die 'stop existing server and clean owned topology first'; fi
run_user() { setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups --reset-env -- env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C "NETEM_SEED=${NETEM_SEED:-default}" "$@" 8>&-; }
support() { run_user python3 scripts/evidence-support.py "$@"; }
run_user python3 scripts/bench-support.py preflight
run_user bash -c 'for tool in ip tc ethtool ping python3 sysctl setpriv rg; do command -v "$tool" >/dev/null || { printf "G11: owner PATH missing %s\n" "$tool" >&2; exit 3; }; done'
run_user bash scripts/tshark.sh -v >/dev/null
run_user mkdir -p results
root="$repo/results/p11-g11-$(run_user python3 -c 'import secrets;print(secrets.token_hex(6))')"
support prepare "$root"
active=false server_pid= client_pid= client_cap= server_cap= ready=
host_snapshot() {
 local kind label=$1
 for kind in link address route; do
  if [[ $kind == route ]]; then ip -j route show table all; else ip -j "$kind" show; fi | run_user tee "$root/host/$kind.$label.json" >/dev/null
 done
}
cleanup() {
 local original=$? clean=0
 trap - EXIT;trap '' INT TERM;set +e
 stop_process "$client_pid" true || clean=1
 stop_process "$server_pid" || clean=1
 stop_process "$client_cap" true 400 || clean=1
 stop_process "$server_cap" true 400 || clean=1
 if [[ $active == true ]]; then
  bash scripts/network/clear-netem.sh | run_user tee "$root/network/cleanup.json" >/dev/null || clean=1
  bash scripts/network/teardown.sh > >(run_user python3 scripts/evidence-support.py sink "$root/logs/teardown.log") || clean=1
 fi
 host_snapshot final || clean=1
 for kind in link address route; do cmp -s "$root/host/$kind.before.json" "$root/host/$kind.final.json" || clean=1; done
 if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER ]]; then clean=1; fi
 support cleanup "$root" "$original" "$clean" || clean=1
 # Evaluate all attempts after sinks, server traces and host cleanup finish.
 if (( original==0 && clean==0 )); then run_user python3 scripts/bench-support.py launch-log "$root/logs/check.log" /usr/bin/python3 "$repo/tests/system/check_g11.py" "$root" || original=$?; fi
 printf 'G11: gate_root=%s original_exit=%s cleanup_exit=%s\n' "$root" "$original" "$clean" 2>/dev/null || true
 (( original!=0 || clean==0 )) || original=1
 exit "$original"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
host_snapshot before
run_user python3 scripts/bench-support.py runtime "$root"
bash scripts/network/setup.sh;active=true
host_snapshot active
for kind in link address route; do cmp -s "$root/host/$kind.before.json" "$root/host/$kind.active.json" || lab_die 'host state changed'; done
probe_seed=default
[[ ${NETEM_SEED:-default} != none ]] || probe_seed=none
for scenario in baseline rtt50-loss0; do
 bash scripts/network/netem.sh --scenario="$scenario" --profile=ingress-ifb --seed="$probe_seed" | run_user tee "$root/network/$scenario-probe.json" >/dev/null
 for ns in qclient qserver; do
  dest=10.10.0.2;[[ $ns != qserver ]] || dest=10.10.0.1
  bash scripts/run-in-netns.sh "$ns" -- ping -n -c 2 -W 2 "$dest" >/dev/null
  log="$root/probes/$scenario-$ns.log"
  bash scripts/run-in-netns.sh "$ns" -- ping -n -c 12 -i .2 -W 2 "$dest" | run_user tee "$log" >/dev/null
  run_user python3 scripts/bench-support.py probe "$log" "$scenario" "$ns"
 done
done
run_trial() {
 local rid=$1 profile=$2 tr=$3 mode=$4 scenario=$5 seed=$6 rc=0 idle=false
 support run "$root" "$rid" "$profile" "$tr" "$mode" "$scenario" "$seed" pending
 bash scripts/network/netem.sh --scenario="$scenario" --profile=ingress-ifb --seed="$seed" | run_user tee "$root/network/$rid.apply.json" >/dev/null
 bash scripts/network/inspect.sh | run_user tee "$root/network/$rid.before.json" >/dev/null
 run_user mkdir "$root/traces/$rid" "$root/captures/$rid"
 ready="$root/traces/$rid/ready"
 bash scripts/run-in-netns.sh qserver -- /usr/bin/python3 "$repo/scripts/bench-support.py" launch-verified "$root/logs/$rid-server.log" "$root" server \
  --transport=both --profile="$profile" --listen=10.10.0.2:4433 --allow-0rtt=true --ready-file="$ready" \
  --qlog-dir="$root/traces/$rid/server-qlog" --keylog="$root/traces/$rid/server.keylog" 8>&- & server_pid=$!
 for ((j=0;j<100;j++)); do [[ -s $ready ]] && break;kill -0 "$server_pid" || lab_die 'server exited';sleep .05;done
 [[ -s $ready && $(stat -c '%u:%g' "/proc/$server_pid") == "$SUDO_UID:$SUDO_GID" ]] || lab_die 'server readiness/UID failed'
 bash scripts/capture.sh qclient "$root/captures/$rid/qclient" 150 & client_cap=$!
 bash scripts/capture.sh qserver "$root/captures/$rid/qserver" 150 & server_cap=$!
 for ((j=0;j<200;j++)); do [[ -f $root/captures/$rid/qclient/ready && -f $root/captures/$rid/qserver/ready ]] && break;sleep .05;done
 [[ -f $root/captures/$rid/qclient/ready && -f $root/captures/$rid/qserver/ready ]] || lab_die 'capture not ready'
 timeout --signal=TERM --kill-after=5s 135s bash scripts/run-in-netns.sh qclient -- /usr/bin/python3 "$repo/scripts/bench-support.py" launch-verified \
  "$root/logs/$rid-client.log" "$root" client --transport="$tr" --mode="$mode" --profile="$profile" --addr=10.10.0.2:4433 --server-name=10.10.0.2 \
  --experiment-id="$(basename "$root")" --run-id="$rid" --out="$root/runs/$rid" --network-state="$root/network/$rid.before.json" \
  --qlog-dir="$root/traces/$rid/client-qlog" --keylog="$root/traces/$rid/client.keylog" --progress --format=json 8>&- & client_pid=$!
 wait "$client_pid" || rc=$?;client_pid=
 support run "$root" "$rid" "$profile" "$tr" "$mode" "$scenario" "$seed" "$rc"
 [[ -f $root/runs/$rid/raw/$rid.json && ! -f $root/runs/$rid/INCOMPLETE && $rc -le 1 ]] || lab_die "incomplete trial $rid (exit$rc)"
 stop_process "$server_pid";server_pid=
 [[ ! -e $ready ]] || lab_die 'ready marker remains'
 stop_process "$client_cap" true 400;client_cap=
 stop_process "$server_cap" true 400;server_cap=
 bash scripts/network/inspect.sh | run_user tee "$root/network/$rid.after.json" >/dev/null
 for ((j=0;j<50;j++)); do
  bash scripts/network/inspect.sh | run_user tee "$root/network/$rid.idle-$j-before.json" >/dev/null;sleep .2
  bash scripts/network/inspect.sh | run_user tee "$root/network/$rid.idle-$j-after.json" >/dev/null
  if run_user python3 scripts/bench-support.py idle "$root/network/$rid.idle-$j-before.json" "$root/network/$rid.idle-$j-after.json"; then idle=true;break;fi
 done
 [[ $idle == true ]] || lab_die 'traffic not idle before reset'
 printf 'G11: run=%s exit=%s\n' "$rid" "$rc" 2>/dev/null || true
}
seed=2026100200;[[ $probe_seed != none ]] || seed=none
for mode in cold resumed early; do run_trial "handshake_$mode" handshake quic "$mode" rtt50-loss0 "$seed";done
# Validate the actual early packet before spending time on twenty bulk runs.
run_user python3 scripts/bench-support.py launch-log "$root/logs/early-check.log" /usr/bin/python3 "$repo/tests/system/check_g11.py" "$root" --early-only
# All ten attempts are retained, with changing seeds and alternating order.
for ((attempt=0;attempt<10;attempt++)); do
 seed=$((2026100201+attempt));[[ $probe_seed != none ]] || seed=none
 order=(tcp quic);(( attempt%2==0 )) || order=(quic tcp)
 for tr in "${order[@]}"; do run_trial "loss_${attempt}_$tr" bulk "$tr" cold rtt50-loss3 "$seed";done
done
