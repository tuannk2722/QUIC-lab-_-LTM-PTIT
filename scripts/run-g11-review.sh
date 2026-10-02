#!/usr/bin/env bash
# Ordinary-user entry: build first, then the authorized privileged G11 wrapper.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID != 0 ]] || { echo 'Run this script as your ordinary WSL user.' >&2; exit 3; }
make build
sudo -v
g11_log=$(mktemp docs/evidence/p11/g11-user-run.XXXXXX.log)
set +e
sudo bash tests/system/run.sh --gate G11 2>&1 | tee "$g11_log"
pipeline_status=("${PIPESTATUS[@]}")
set -e
g11_status=${pipeline_status[0]}
printf 'g11_exit=%s\nlog=%s\n' "$g11_status" "$g11_log" | tee -a "$g11_log"
(( pipeline_status[1] == 0 )) || { echo 'Evidence log write failed.' >&2; exit 1; }
exit "$g11_status"
