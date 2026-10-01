#!/usr/bin/env bash
# Remove only namespaces whose identities match the root-owned marker.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/common.sh"
require_sudo_caller
if [[ ! -e $LAB_STATE_DIR ]]; then
    if namespace_exists qclient || namespace_exists qserver; then
        lab_die 'qclient or qserver exists without lab state; refusing deletion'
    fi
    printf 'P7 topology already absent\n'
    exit 0
fi
check_state_dir
exec 9>"$LAB_STATE_DIR/lock"
flock -x 9
if [[ ! -e $LAB_MARKER && ! -L $LAB_MARKER ]]; then
    if namespace_exists qclient || namespace_exists qserver; then
        lab_die 'qclient or qserver exists without ownership marker; refusing deletion'
    fi
    printf 'P7 topology already absent\n'
    exit 0
fi
require_owned_resources

for ns in qclient qserver; do
    if namespace_exists "$ns"; then
        pids=$(ip netns pids "$ns")
        [[ -z $pids ]] || lab_die "$ns has processes ($pids); stop only lab-managed processes first"
    fi
done
for ns in qserver qclient; do
    if namespace_exists "$ns"; then
        ip netns delete "$ns"
    fi
done
rm -- "$LAB_MARKER"
printf 'P7 owned topology removed; verify host link/address/route snapshots for G07\n'
