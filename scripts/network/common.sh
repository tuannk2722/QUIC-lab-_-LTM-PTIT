#!/usr/bin/env bash
# Shared, root-only ownership checks for the fixed P7 topology.
LAB_STATE_DIR=/run/quic-performance-lab
LAB_MARKER=$LAB_STATE_DIR/topology-v1
LAB_NETNS_DIR=/run/netns

lab_error() { printf 'network: %s\n' "$*" >&2; }
lab_die() { lab_error "$*"; exit 3; }

require_sudo_caller() {
    (( EUID == 0 )) || lab_die 'run through sudo; network setup/entry requires root'
    [[ ${SUDO_UID:-} =~ ^[0-9]+$ && ${SUDO_GID:-} =~ ^[0-9]+$ ]] ||
        lab_die 'SUDO_UID and SUDO_GID are required to identify the unprivileged owner'
    (( SUDO_UID > 0 && SUDO_GID > 0 )) || lab_die 'the application owner must be non-root'
    getent passwd "$SUDO_UID" >/dev/null || lab_die 'sudo caller UID has no passwd entry'
}

check_state_dir() {
    [[ -d $LAB_STATE_DIR && ! -L $LAB_STATE_DIR ]] || lab_die 'state directory is absent or unsafe'
    [[ $(stat -c '%u:%a' "$LAB_STATE_DIR") == 0:700 ]] ||
        lab_die 'state directory must be root-owned mode 0700'
}

namespace_exists() {
    [[ -e $LAB_NETNS_DIR/$1 || -L $LAB_NETNS_DIR/$1 ]]
}

namespace_identity() {
    stat -Lc '%d:%i' "$LAB_NETNS_DIR/$1"
}

link_is_up() {
    local flags=${1#*<}
    [[ $flags != "$1" ]] || return 1
    flags=${flags%%>*}
    [[ ,$flags, == *,UP,* ]]
}

read_owned_marker() {
    require_sudo_caller
    check_state_dir
    [[ -f $LAB_MARKER && ! -L $LAB_MARKER ]] || lab_die 'ownership marker missing or unsafe'
    [[ $(stat -c '%u:%a' "$LAB_MARKER") == 0:600 ]] ||
        lab_die 'ownership marker must be root-owned mode 0600'
    local -a fields=()
    mapfile -t fields < "$LAB_MARKER"
    [[ ${#fields[@]} == 5 && ${fields[0]} == quic-lab-topology-v1 &&
       ${fields[1]} == "$SUDO_UID" && ${fields[2]} == "$SUDO_GID" &&
       ${fields[3]} =~ ^[0-9]+:[0-9]+$ && ${fields[4]} =~ ^[0-9]+:[0-9]+$ ]] ||
        lab_die 'ownership marker is malformed or belongs to another sudo caller'
    LAB_CLIENT_ID=${fields[3]}
    LAB_SERVER_ID=${fields[4]}
}

# Used by teardown after a partially completed delete. Never authorizes a
# namespace whose current identity differs from the root-owned marker.
require_owned_resources() {
    read_owned_marker
    if namespace_exists qclient; then
        [[ $(namespace_identity qclient) == "$LAB_CLIENT_ID" ]] ||
            lab_die 'qclient identity differs from marker; refusing deletion'
    fi
    if namespace_exists qserver; then
        [[ $(namespace_identity qserver) == "$LAB_SERVER_ID" ]] ||
            lab_die 'qserver identity differs from marker; refusing deletion'
    fi
}

require_owned_topology() {
    require_owned_resources
    namespace_exists qclient && namespace_exists qserver ||
        lab_die 'owned topology is incomplete; run teardown before setup'
    local ns ip link addresses
    for ns in qclient qserver; do
        if [[ $ns == qclient ]]; then ip=10.10.0.1/24; else ip=10.10.0.2/24; fi
        link=$(ip -n "$ns" -o link show dev eth0) || lab_die "$ns eth0 missing"
        [[ $link == *'mtu 1500 '* ]] && link_is_up "$link" ||
            lab_die "$ns eth0 MTU/up state differs from topology"
        addresses=$(ip -n "$ns" -o -4 addr show dev eth0) || lab_die "$ns IPv4 missing"
        [[ $addresses == *"inet $ip "* ]] || lab_die "$ns IPv4 address differs from topology"
        link=$(ip -n "$ns" -o link show dev lo) || lab_die "$ns loopback missing"
        link_is_up "$link" || lab_die "$ns loopback is down"
        link=$(ip -n "$ns" -o link show dev ifb0) || lab_die "$ns ifb0 missing"
        link_is_up "$link" || lab_die "$ns ifb0 is down"
    done
}
