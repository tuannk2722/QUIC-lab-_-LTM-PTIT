#!/usr/bin/env bash
# P10 gate: actual functional cases + 90 measured handshake targets via IFB.
set -euo pipefail
cd "$(dirname "$0")/../.."
repo=$(pwd -P)
source scripts/network/common.sh
require_sudo_caller
[[ $# == 0 ]] || { echo 'G10 takes no repeat-count overrides' >&2; exit 2; }
run_user() { setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups -- "$@"; }
run_user mkdir -p results
gate_root=$(run_user mktemp -d "$repo/results/p10-g10-XXXXXX")
echo "G10: gate_root=$gate_root UTC=$(date -u +%FT%TZ) apps_uid_gid=$SUDO_UID:$SUDO_GID"
run_user mkdir "$gate_root/functional"
run_user env GOTOOLCHAIN=local GOPATH="$repo/.tools/gopath" GOCACHE="$repo/.tools/gocache" GOMAXPROCS=2 GOFLAGS=-p=2 \
    QUICLAB_G10_RECORDS="$gate_root/functional" "$repo/.tools/go1.27.1/bin/go" test -mod=readonly -count=1 -v \
    -run '^TestSession' ./tests/integration 2>&1 | run_user tee "$gate_root/functional-tests.log"
run_user python3 tests/system/check_g10.py "$gate_root/functional" --functional
case_args=(--suite=handshake)
if [[ ${NETEM_SEED:-default} == none ]]; then case_args+=(--disable-netem-seed); fi
main_rc=0
bash scripts/bench.sh --out="$gate_root/main" "${case_args[@]}" || main_rc=$?
(( main_rc <= 1 )) || { echo "G10 environment/runtime exit=$main_rc" >&2; exit "$main_rc"; }
run_user python3 tests/system/check_g10.py "$gate_root/main"
run_user python3 - "$gate_root" "$main_rc" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
data={'gate':'G10','status':'PASS','scope':'P10 functional and actual handshake cohort; packet corroboration belongs to P11',
      'main_exit':int(sys.argv[2]),'main':str(root/'main'),'functional':str(root/'functional'),
      'packet_0rtt_proof':'NOT_RUN: API state/timing alone does not prove captured 0-RTT app request'}
(root/'gate-summary.json').write_text(json.dumps(data,indent=2)+'\n')
PY
echo "G10 P10 PASS: gate_root=$gate_root main_exit=$main_rc packet-proof=P11-pending"
