#!/usr/bin/env bash
# Full G09: interrupted actual trial + all default main performance entries.
set -euo pipefail
cd "$(dirname "$0")/../.."
repo=$(pwd -P)
source scripts/network/common.sh
require_sudo_caller
[[ $# == 0 ]] || { echo 'G09 takes no repeat-count overrides' >&2; exit 2; }
run_user() { setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups -- "$@"; }
run_user mkdir -p results
# Container directories own the two separately immutable experiments.
gate_root=$(run_user mktemp -d "$repo/results/p9-g09-XXXXXX")
echo "G09: gate_root=$gate_root UTC=$(date -u +%FT%TZ)"
case_args=()
if [[ ${NETEM_SEED:-default} == none ]]; then case_args+=(--disable-netem-seed); fi
interrupt_rc=0
bash scripts/bench.sh --out="$gate_root/interrupt" --interrupt-case "${case_args[@]}" || interrupt_rc=$?
[[ $interrupt_rc == 130 ]] || { echo "G09 FAIL: interrupt exit $interrupt_rc expected130" >&2; exit 1; }
run_user python3 tests/system/check_g09.py "$gate_root/interrupt" --interrupted
main_rc=0
bash scripts/bench.sh --out="$gate_root/main" "${case_args[@]}" || main_rc=$?
(( main_rc <= 1 )) || { echo "G09 environment/runtime exit=$main_rc" >&2; exit "$main_rc"; }
run_user python3 tests/system/check_g09.py "$gate_root/main"
run_user python3 - "$gate_root" "$main_rc" "$interrupt_rc" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
data={'gate':'G09','status':'PASS','main_exit':int(sys.argv[2]),'interrupt_exit':int(sys.argv[3]),
      'main':str(root/'main'),'interrupt':str(root/'interrupt'),
      'notes':'256 main scheduled invocations including failed transfers; actual interrupt/missing rows, network/cleanup/summary/plots verified. No superiority/HOL proof gate.'}
(root/'gate-summary.json').write_text(json.dumps(data,indent=2)+'\n')
PY
echo "G09 PASS: gate_root=$gate_root main_exit=$main_rc interrupted_exit=$interrupt_rc"
