#!/usr/bin/env bash
# One-time recovery for host IFBs created by the first failed G07 run.
# Requires that the current host state still matches that run's snapshots.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/common.sh"
check_only=false
if [[ ${1:-} == --check-only ]]; then
    check_only=true
    shift
else
    require_sudo_caller
fi
[[ $# == 1 ]] || { lab_error 'usage: [sudo] bash scripts/network/restore-host-ifb.sh [--check-only] RESULTS_DIR/host-state'; exit 2; }
snapshot_dir=$(realpath -e -- "$1")
[[ -d $snapshot_dir ]] || lab_die 'host-state snapshot directory missing'
if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER || -L $LAB_MARKER ]]; then
    lab_die 'lab namespace or marker still exists; refusing host IFB recovery'
fi

check_host_state() {
python3 - "$snapshot_dir" "$1" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

snapshots = Path(sys.argv[1])
target = sys.argv[2]

def saved(kind, label):
    return json.loads((snapshots / f"{kind}.{label}.json").read_text())

def live(*args):
    return json.loads(subprocess.check_output(["ip", "-j", *args], text=True))

def tc(*args):
    return json.loads(subprocess.check_output(["tc", "-j", *args], text=True))

def require_no_filters(name):
    for parent in ((), ("ingress",), ("egress",)):
        if tc("filter", "show", "dev", name, *parent):
            raise SystemExit(f"{name} has host tc filters that could reference an IFB; refusing recovery")

before_links = saved("link", "before")
active_links = saved("link", "pass1-active")
if [row for row in active_links if row["ifname"] not in {"ifb0", "ifb1"}] != before_links:
    raise SystemExit("snapshot contains an unexpected host-link change")
extras = {row["ifname"]: row for row in active_links if row["ifname"] in {"ifb0", "ifb1"}}
if set(extras) != {"ifb0", "ifb1"}:
    raise SystemExit("expected exactly two additional host IFBs")
current_links = live("link", "show")
present = {row["ifname"] for row in current_links} & extras.keys()
expected_links = [row for row in active_links if row["ifname"] not in extras or row["ifname"] in present]
if current_links != expected_links:
    raise SystemExit("host links differ from the failed G07 snapshot or its partially recovered state")
for name in present:
    row = extras[name]
    if row["flags"] != ["BROADCAST", "NOARP"] or row["operstate"] != "DOWN" or row["qdisc"] != "noop":
        raise SystemExit(f"{name} is active or configured; refusing recovery")
    details = live("-d", "link", "show", "dev", name)
    if len(details) != 1 or details[0].get("ifindex") != row["ifindex"] or details[0].get("address") != row["address"] or details[0].get("linkinfo", {}).get("info_kind") != "ifb":
        raise SystemExit(f"{name} identity/type differs from the failed G07 snapshot")
    qdiscs = tc("qdisc", "show", "dev", name)
    if qdiscs and not (len(qdiscs) == 1 and qdiscs[0].get("kind") == "noop" and qdiscs[0].get("root") is True):
        raise SystemExit(f"{name} has a tc qdisc; refusing recovery")
    require_no_filters(name)
for row in before_links:
    require_no_filters(row["ifname"])

before_addresses = saved("address", "before")
active_addresses = saved("address", "pass1-active")
if [row for row in active_addresses if row["ifname"] not in extras] != before_addresses:
    raise SystemExit("snapshot contains an unexpected host-address change")
if any(row.get("addr_info") for row in active_addresses if row["ifname"] in present):
    raise SystemExit("host IFB acquired an address; refusing recovery")
expected_addresses = [row for row in active_addresses if row["ifname"] not in extras or row["ifname"] in present]
if live("address", "show") != expected_addresses:
    raise SystemExit("host addresses differ from the failed G07 snapshot or its partially recovered state")

before_routes = saved("route", "before")
active_routes = saved("route", "pass1-active")
if active_routes != before_routes or live("route", "show", "table", "all") != before_routes:
    raise SystemExit("host routes differ from the original snapshot")
print("present" if target in present else "absent")
PY
}

if [[ $check_only == true ]]; then
    for name in ifb0 ifb1; do
        state=$(check_host_state "$name")
        printf '%s: %s; host matches failed G07 snapshots and has no IFB tc configuration\n' "$name" "$state"
    done
    printf 'CHECK ONLY: no host device was changed\n'
    exit 0
fi

for name in ifb0 ifb1; do
    # Recheck the exact current link, address, route, IFB type and tc state
    # immediately before each deletion. A second run can finish a partial delete.
    state=$(check_host_state "$name")
    if [[ $state == present ]]; then
        ip link delete dev "$name"
    fi
done
[[ $(check_host_state ifb0) == absent && $(check_host_state ifb1) == absent ]] ||
    lab_die 'host IFBs still present after recovery'
ip -j link show | cmp -s - "$snapshot_dir/link.before.json" || lab_die 'host links did not return to original snapshot'
ip -j address show | cmp -s - "$snapshot_dir/address.before.json" || lab_die 'host addresses did not return to original snapshot'
ip -j route show table all | cmp -s - "$snapshot_dir/route.before.json" || lab_die 'host routes did not return to original snapshot'
printf 'PASS: failed-run host IFBs absent; host link/address/route match original snapshots\n'
