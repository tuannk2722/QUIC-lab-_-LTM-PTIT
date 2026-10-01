#!/usr/bin/env bash
# Create only qclient/qserver resources owned by this lab and sudo caller.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/common.sh"
require_sudo_caller
umask 077

if [[ ! -e $LAB_STATE_DIR ]]; then
    mkdir -m 0700 -- "$LAB_STATE_DIR"
fi
check_state_dir
exec 9>"$LAB_STATE_DIR/lock"
flock -x 9

if [[ -e $LAB_MARKER || -L $LAB_MARKER ]]; then
    require_owned_topology
    printf 'P7 topology already ready and owned by UID %s: qclient, qserver\n' "$SUDO_UID"
    exit 0
fi
if namespace_exists qclient || namespace_exists qserver; then
    lab_die 'qclient or qserver exists without this lab ownership marker; refusing collision'
fi

created_client=false
created_server=false
marker_created=false
client_id=
server_id=
tmp_marker=
rollback() {
    local rc=$? ns expected
    trap - EXIT
    if (( rc != 0 )); then
        [[ -z $tmp_marker ]] || rm -f -- "$tmp_marker"
        if [[ $marker_created == true ]]; then
            rm -- "$LAB_MARKER" || lab_error 'rollback could not remove ownership marker'
        fi
        for ns in qserver qclient; do
            if [[ $ns == qserver ]]; then
                [[ $created_server == true ]] || continue
                expected=$server_id
            else
                [[ $created_client == true ]] || continue
                expected=$client_id
            fi
            if namespace_exists "$ns"; then
                if [[ -n $expected && $(namespace_identity "$ns") == "$expected" ]]; then
                    ip netns delete "$ns" || lab_error "rollback could not delete $ns"
                else
                    lab_error "rollback left $ns because its identity is unverified"
                fi
            fi
        done
    fi
    exit "$rc"
}
trap rollback EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Loading ifb through the first `ip link add ... type ifb` uses the kernel's
# legacy numifbs=2 default and creates ifb0/ifb1 in init_net (the host).
# Load it explicitly with zero legacy host devices before namespace IFBs.
host_links_before=$(ip -j link show)
modprobe ifb numifbs=0
host_links_after=$(ip -j link show)
[[ $host_links_after == "$host_links_before" ]] ||
    lab_die 'loading ifb changed host links; refusing to continue (inspect host IFBs)'

ip netns add qclient
created_client=true
client_id=$(namespace_identity qclient)
if [[ ${QUICLAB_FAIL_AFTER:-} == client-namespace ]]; then
    lab_error 'injected setup failure after qclient creation'
    exit 1
fi
ip netns add qserver
created_server=true
server_id=$(namespace_identity qserver)

ip -n qclient link add vc0 type veth peer name vs0
ip -n qclient link set dev vs0 netns qserver
ip -n qclient link set dev vc0 name eth0
ip -n qserver link set dev vs0 name eth0
for ns in qclient qserver; do
    ip -n "$ns" link set dev lo up
    ip -n "$ns" link set dev eth0 mtu 1500 up
    ip -n "$ns" link add ifb0 type ifb
    ip -n "$ns" link set dev ifb0 up
done
ip -n qclient addr add 10.10.0.1/24 dev eth0
ip -n qserver addr add 10.10.0.2/24 dev eth0

tmp_marker=$(mktemp "$LAB_STATE_DIR/.topology-v1.XXXXXXXX")
printf 'quic-lab-topology-v1\n%s\n%s\n%s\n%s\n' \
    "$SUDO_UID" "$SUDO_GID" "$client_id" "$server_id" > "$tmp_marker"
chmod 0600 "$tmp_marker"
ln -- "$tmp_marker" "$LAB_MARKER" # atomic and refuses overwrite
marker_created=true
rm -- "$tmp_marker"
tmp_marker=
require_owned_topology
printf 'P7 topology ready: qclient=10.10.0.1/24 qserver=10.10.0.2/24 eth0 MTU=1500 ifb0=up owner_uid=%s\n' "$SUDO_UID"
