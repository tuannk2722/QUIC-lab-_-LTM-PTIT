#!/usr/bin/env bash
# Disposable P0 capability check only: no application processes or host NIC changes.
set -euo pipefail
if [[ $EUID != 0 ]]; then echo 'Run sudo bash scripts/preflight-network.sh for the scoped capability probe.' >&2; exit 3; fi
ns="qp0-$$-$RANDOM"
created=false
cleanup() {
    rc=$?
    trap - EXIT
    if [[ $created == true ]]; then
        if ! ip netns delete "$ns"; then echo "BLOCKED: cleanup failed for $ns" >&2; rc=3; fi
    fi
    if [[ $rc != 0 && $rc != 130 && $rc != 143 ]]; then rc=3; fi
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
echo "P0 capability probe UTC=$(date -u +%FT%TZ) namespace=$ns"
ip netns add "$ns"
created=true
ip -n "$ns" link add p0a type veth peer name p0b
ip -n "$ns" link set p0a up
ip -n "$ns" link set p0b up
ip -n "$ns" link add ifb0 type ifb
ip -n "$ns" link set ifb0 up
ip netns exec "$ns" tc qdisc add dev p0a handle ffff: ingress
ip netns exec "$ns" tc filter add dev p0a parent ffff: protocol ip u32 match u32 0 0 action mirred egress redirect dev ifb0
ip netns exec "$ns" tc qdisc add dev ifb0 root netem delay 50ms
ip netns exec "$ns" tc -s qdisc show dev ifb0
ip netns exec "$ns" tc filter show dev p0a parent ffff:
ip netns delete "$ns"
created=false
echo 'PASS: netns create/delete, veth, IFB up, ingress mirred filter and 50ms netem attach.'
echo 'No traffic/RTT/rate/counter methodology verified; G07/G08 NOT_RUN.'
