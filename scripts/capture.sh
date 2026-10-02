#!/usr/bin/env bash
# Managed capture on an owned namespace eth0. Only tcpdump/socket/entry need
# privilege. The output sinks create exclusive files as the ordinary owner.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/network/common.sh
source scripts/process-lifecycle.sh
require_sudo_caller
[[ $# == 3 && ($1 == qclient || $1 == qserver) && $3 =~ ^[0-9]+$ ]] || { echo 'Usage: sudo bash scripts/capture.sh qclient|qserver NEW_DIR DURATION_SECONDS' >&2; exit 2; }
ns=$1 out=$2 duration=$3
(( duration >= 1 && duration <= 300 )) || exit 2
require_owned_topology
for tool in ip tcpdump python3 setpriv rg; do command -v "$tool" >/dev/null || lab_die "missing $tool"; done
exec 8>&-
run_user() { setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups --reset-env -- env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C "$@" 8>&- 9>&-; }
run_user mkdir -- "$out"
run_user mkfifo -m 600 "$out/.packets" "$out/.log"
pid= timer= packets= logger=
run_sink() { exec setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups --reset-env -- env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C python3 scripts/evidence-support.py sink "$1" 8>&- 9>&-; }
cleanup() {
 local original=$? rc=0
 trap - EXIT; trap '' INT TERM
 set +e
 [[ -z $timer ]] || { kill -TERM "$timer" 2>/dev/null; wait "$timer" 2>/dev/null; }
 if [[ -n $pid ]]; then
  # Outside client timing: allow the immediate-mode reader to consume queued
  # packets, flush the dump, then stop it and wait for the sinks' EOF/fsync.
  if managed_process_running "$pid"; then
   sleep .2
   kill -USR2 "$pid" 2>/dev/null || true
  fi
  kill -INT "$pid" 2>/dev/null
  wait_managed_process "$pid" 100 .05; child=$?; (( child==0 || child==130 )) || rc=1
 fi
 if [[ -n $packets ]]; then wait_managed_process "$packets" 250 .02 || rc=1; fi
 if [[ -n $logger ]]; then wait_managed_process "$logger" 250 .02 || rc=1; fi
 run_user rm -f -- "$out/.packets" "$out/.log" "$out/ready"
 run_user python3 scripts/evidence-support.py capture-status "$out" "$ns" "$original" "$rc" || rc=1
 if (( rc != 0 && (original == 0 || original == 130 || original == 143) )); then original=1; fi
 exit "$original"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
run_sink "$out/capture.pcap" < "$out/.packets" & packets=$!
run_sink "$out/tcpdump.log" < "$out/.log" & logger=$!
owner=$(getent passwd "$SUDO_UID" | cut -d: -f1)
ip netns exec "$ns" tcpdump --immediate-mode -p -n -i eth0 -s 0 -U -Z "$owner" -w - 'ip and (tcp port 4433 or udp port 4433)' > "$out/.packets" 2> "$out/.log" 8>&- 9>&- & pid=$!
for ((i=0;i<100;i++)); do
 [[ ! -f $out/tcpdump.log ]] || if rg -q 'listening on eth0' "$out/tcpdump.log"; then break; fi
 kill -0 "$pid" 2>/dev/null || exit 3
 sleep 0.05
done
rg -q 'listening on eth0' "$out/tcpdump.log" || exit 3
run_user touch "$out/ready"
python3 -c 'import os,signal,sys,time; time.sleep(int(sys.argv[1])); os.kill(int(sys.argv[2]),signal.SIGINT)' "$duration" "$pid" 8>&- 9>&- & timer=$!
wait "$pid"; pid=
