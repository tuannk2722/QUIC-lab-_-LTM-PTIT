#!/usr/bin/env bash
# G07 system gate. Run after an unprivileged build: sudo bash tests/system/run.sh
# The caller may tee stdout/stderr to an evidence log; this script creates no
# root-owned files in the repository. Client result directories belong to the
# original sudo caller.
set -euo pipefail

if [[ $# -gt 0 ]]; then
    if [[ $# == 2 && $1 == --gate && $2 == G08 ]]; then
        exec bash "$(dirname "$0")/g08.sh"
    fi
    echo 'Usage: sudo bash tests/system/run.sh [--gate G08]' >&2
    exit 2
fi

cd "$(dirname "$0")/../.."
repo=$(pwd -P)
marker=/run/quic-performance-lab/topology-v1
server_pid=
topology_active=false
foreign_created=false
case_dir=
host_dir=

fail() { echo "G07 FAIL: $*" >&2; exit 1; }
say() { echo "G07: $*"; }
run_user() {
    setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups -- "$@"
}
ns_exists() {
    [[ -e /run/netns/$1 || -L /run/netns/$1 ]]
}
assert_absent() {
    if ns_exists qclient || ns_exists qserver; then
        fail 'qclient/qserver namespace remains after cleanup'
    fi
    [[ ! -e $marker && ! -L $marker ]] || fail "ownership marker remains: $marker"
}
assert_no_pids() {
    local ns
    for ns in qclient qserver; do
        [[ -z $(ip netns pids "$ns") ]] || fail "orphan process in $ns"
    done
}
stop_server() {
    local sig=${1:-TERM} tries forced=false status
    [[ -n $server_pid ]] || return 0
    kill -s "$sig" "$server_pid" 2>/dev/null || true
    for ((tries=0; tries<100; tries++)); do
        if ! server_running; then break; fi
        sleep 0.1
    done
    if server_running; then
        forced=true
        kill -s KILL "$server_pid" 2>/dev/null || true
    fi
    if wait "$server_pid"; then status=0; else status=$?; fi
    say "managed server signal=$sig exit=$status forced_kill=$forced"
    server_pid=
    [[ $forced == false && ( $sig != INT || $status -eq 0 ) ]]
}
server_running() {
    local state
    kill -0 "$server_pid" 2>/dev/null || return 1
    state=$(awk '{print $3}' "/proc/$server_pid/stat" 2>/dev/null) || return 1
    [[ $state != Z && $state != X ]]
}
cleanup() {
    local rc=$?
    trap - EXIT INT TERM
    if ! stop_server TERM; then rc=1; fi
    if [[ $topology_active == true ]]; then
        if ! bash scripts/network/teardown.sh; then rc=1; fi
    fi
    if [[ $foreign_created == true ]]; then
        if ! ip netns delete qclient; then rc=1; fi
    fi
    if [[ -n $case_dir ]]; then say "results_dir=$case_dir"; fi
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ $EUID -eq 0 ]] || { echo 'Run: sudo bash tests/system/run.sh' >&2; exit 3; }
[[ ${SUDO_UID:-} =~ ^[0-9]+$ && ${SUDO_GID:-} =~ ^[0-9]+$ ]] || fail 'sudo caller UID/GID required'
[[ $SUDO_UID -ne 0 && $SUDO_GID -ne 0 ]] || fail 'the application must run as a non-root sudo caller'
for tool in ip modprobe ping setpriv python3 stat awk grep cmp diff sha256sum tee; do
    command -v "$tool" >/dev/null || fail "missing $tool"
done
[[ -x bin/server && -x bin/client ]] || fail 'build as the normal user first: make build'
run_user test -r certs/server.crt || fail 'certificate unreadable to caller; run make certs as the normal user'
run_user test -r certs/server.key || fail 'private key unreadable to caller; run make certs as the normal user'
run_user mkdir -p -- results
run_user test -w results || fail 'results/ must be writable by the sudo caller'
ip netns list >/dev/null || { echo 'network namespace inspection denied' >&2; exit 3; }
if ns_exists qclient || ns_exists qserver || [[ -e $marker || -L $marker ]]; then
    fail 'existing lab names or marker; review ownership before running the destructive system gate'
fi

case_dir=$(run_user mktemp -d "$repo/results/p7-g07-XXXXXX")
host_dir=$case_dir/host-state
run_user mkdir -- "$host_dir"
say "UTC=$(date -u +%FT%TZ) repo=$repo root_uid=$EUID app_uid=$SUDO_UID app_gid=$SUDO_GID"
say "results_dir=$case_dir"

snapshot_host() {
    local label=$1
    ip -j link show | run_user tee "$host_dir/link.$label.json" >/dev/null
    ip -j address show | run_user tee "$host_dir/address.$label.json" >/dev/null
    ip -j route show table all | run_user tee "$host_dir/route.$label.json" >/dev/null
}
compare_host() {
    local label=$1 kind
    snapshot_host "$label"
    for kind in link address route; do
        if ! cmp -s "$host_dir/$kind.before.json" "$host_dir/$kind.$label.json"; then
            diff -u "$host_dir/$kind.before.json" "$host_dir/$kind.$label.json" >&2 || true
            fail "host $kind state changed at $label"
        fi
        say "host-$kind before/$label identical sha256=$(sha256sum "$host_dir/$kind.before.json" | awk '{print $1}')"
    done
}
snapshot_host before

# A foreign namespace with the reserved name must remain untouched.
say 'collision test: create a foreign qclient namespace'
ip netns add qclient
foreign_created=true
if bash scripts/network/setup.sh; then fail 'setup accepted a foreign qclient namespace'; fi
ns_exists qclient || fail 'setup deleted the foreign qclient namespace'
if ns_exists qserver || [[ -e $marker || -L $marker ]]; then fail 'collision left a partial lab topology'; fi
ip netns delete qclient
foreign_created=false
assert_absent
compare_host collision

# Failure after the first namespace is made must roll back it and its marker.
say 'injected setup failure after client-namespace'
if QUICLAB_FAIL_AFTER=client-namespace bash scripts/network/setup.sh; then
    fail 'injected setup failure unexpectedly succeeded'
fi
assert_absent
compare_host partial-failure

inspect_topology() {
    local ns ipaddr uid gid
    for ns in qclient qserver; do
        if [[ $ns == qclient ]]; then ipaddr=10.10.0.1; else ipaddr=10.10.0.2; fi
        ip -n "$ns" -4 -o address show dev eth0 | grep -Fq "inet $ipaddr/24 " || fail "$ns IPv4 address"
        ip -n "$ns" link show dev eth0 | grep -Fq 'mtu 1500' || fail "$ns eth0 MTU"
        ip -n "$ns" link show dev eth0 | grep -Eq '<[^>]*UP' || fail "$ns eth0 is down"
        ip -n "$ns" link show dev lo | grep -Eq '<[^>]*UP' || fail "$ns loopback is down"
        ip -n "$ns" link show dev ifb0 | grep -Eq '<[^>]*UP' || fail "$ns ifb0 is down"
        uid=$(bash scripts/run-in-netns.sh "$ns" -- /usr/bin/id -u)
        gid=$(bash scripts/run-in-netns.sh "$ns" -- /usr/bin/id -g)
        [[ $uid == "$SUDO_UID" && $gid == "$SUDO_GID" ]] || fail "$ns process did not drop UID/GID: $uid:$gid"
        say "$ns eth0=$ipaddr/24 mtu=1500 lo/eth0/ifb0=UP app_uid_gid=$uid:$gid"
    done
    bash scripts/run-in-netns.sh qclient -- "$(command -v ping)" -n -c 3 -W 2 10.10.0.2
    bash scripts/run-in-netns.sh qserver -- "$(command -v ping)" -n -c 3 -W 2 10.10.0.1
}

start_server() {
    local ready=$1 tries
    bash scripts/run-in-netns.sh qserver -- "$repo/bin/server" \
        --transport=both --profile=bulk --listen=10.10.0.2:4433 \
        --ready-file="$ready" &
    server_pid=$!
    for ((tries=0; tries<100; tries++)); do
        if [[ -s $ready ]]; then break; fi
        if ! kill -0 "$server_pid" 2>/dev/null; then fail 'server exited before readiness'; fi
        sleep 0.1
    done
    [[ -s $ready ]] || fail 'server readiness timeout'
    grep -Fq 'tcp=10.10.0.2:4433 udp=10.10.0.2:4433' "$ready" || fail 'both listeners not ready on lab address/port'
    [[ $(stat -c '%u:%g' "/proc/$server_pid") == "$SUDO_UID:$SUDO_GID" ]] ||
        fail 'server process did not drop to the sudo caller UID/GID'
    say "managed_server_pid=$server_pid ready=$(cat "$ready")"
}

run_transfer() {
    local pass=$1 transport=$2 output="$case_dir/${2}-pass${1}"
    say "pass=$pass transport=$transport begin"
    bash scripts/run-in-netns.sh qclient -- "$repo/bin/client" \
        --transport="$transport" --mode=cold --profile=bulk \
        --addr=10.10.0.2:4433 --server-name=10.10.0.2 \
        --ca="$repo/certs/server.crt" --format=json \
        --experiment-id=p7_g07 --run-id="${transport}_pass${pass}" \
        --out="$output"
    run_user python3 analysis/validate.py "$output"
    run_user python3 - "$output" "$transport" "$SUDO_UID" "$SUDO_GID" <<'PY'
import csv
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
transport = sys.argv[2]
uid, gid = map(int, sys.argv[3:5])
with (root / 'runs.csv').open(newline='') as source:
    runs = list(csv.DictReader(source))
with (root / 'streams.csv').open(newline='') as source:
    streams = list(csv.DictReader(source))
assert len(runs) == 1 and runs[0]['success'] == 'true'
assert runs[0]['transport'] == transport
assert runs[0]['bytes_received'] == '6291456'
assert len(streams) == 6 and all(row['success'] == 'true' and row['checksum_ok'] == 'true' for row in streams)
assert os.stat(root).st_uid == uid and os.stat(root).st_gid == gid
print(f'G07 {transport}: 6 resources, 6291456 bytes, all checksums true, output uid:gid={uid}:{gid}')
PY
}

for pass in 1 2; do
    say "topology pass=$pass setup"
    topology_active=true
    bash scripts/network/setup.sh
    [[ -e $marker && ! -L $marker ]] || fail 'setup did not publish a regular ownership marker'
    bash scripts/network/setup.sh
    inspect_topology
    compare_host "pass${pass}-active"
    ready="$case_dir/ready-pass${pass}"
    start_server "$ready"
    run_transfer "$pass" tcp
    run_transfer "$pass" quic
    say "pass=$pass managed Ctrl+C (SIGINT)"
    stop_server INT || fail 'server ignored SIGINT and required SIGKILL'
    [[ ! -e $ready ]] || fail 'server left its readiness file after SIGINT'
    assert_no_pids
    bash scripts/network/teardown.sh
    topology_active=false
    bash scripts/network/teardown.sh
    assert_absent
    compare_host "pass${pass}-teardown"
done

say 'PASS: G07 collision, partial rollback, two topology cycles, UID drop, ping, TCP+QUIC, SIGINT cleanup, unchanged host state'
