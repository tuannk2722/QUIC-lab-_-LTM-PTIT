#!/usr/bin/env bash
# Enter a lab-owned namespace as root, then run the requested command as the
# original sudo caller. The child owns its own signals and output files.
set -euo pipefail

usage() {
    echo 'Usage: sudo bash scripts/run-in-netns.sh qclient|qserver -- command [args...]' >&2
    exit 2
}

[[ $# -ge 3 && ${2-} == -- ]] || usage
ns=$1
shift 2
case "$ns" in
    qclient|qserver) ;;
    *) usage ;;
esac
[[ -n ${1-} ]] || usage
if [[ $EUID != 0 ]]; then
    echo 'Namespace entry requires sudo.' >&2
    exit 3
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# The common check ties both namespace identities and the veth topology to
# the marker created by setup, and checks the sudo caller against its owner.
source "$script_dir/network/common.sh"
require_owned_topology

# exec preserves foreground signal behavior; no unrelated process is killed.
exec ip netns exec "$ns" setpriv \
    --reuid="$SUDO_UID" --regid="$SUDO_GID" --clear-groups --reset-env -- \
    env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "$@"
