#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/common.sh"
require_sudo_caller
check_state_dir
exec 9>"$LAB_STATE_DIR/lock"
flock -x 9
require_owned_topology
exec python3 "$SCRIPT_DIR/state.py" clear "$@"
