#!/usr/bin/env bash
# Offline decoder only; no capture or system install. Prefer system tshark.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd -P)
if command -v tshark >/dev/null; then exec tshark "$@"; fi
local_bin="$repo/.tools/tshark/root/usr/bin/tshark"
[[ -x $local_bin ]] || { echo 'Install tshark or prepare the local decoder; see docs/evidence/p11/README.md' >&2; exit 3; }
export LD_LIBRARY_PATH="$repo/.tools/tshark/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export WIRESHARK_DATA_DIR="$repo/.tools/tshark/root/usr/share/wireshark"
exec "$local_bin" "$@"
