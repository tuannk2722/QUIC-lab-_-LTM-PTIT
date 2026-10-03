#!/usr/bin/env bash
# Prepared fresh source -> actual public Make demos -> timed offline walkthrough.
set -euo pipefail
export LC_ALL=C
unset QLOGDIR
cd "$(dirname "$0")/../.."
repo=$(pwd -P)
source scripts/network/common.sh
require_sudo_caller
[[ $# == 0 ]] || { echo 'G12 accepts no count/time overrides' >&2; exit 2; }
[[ -n ${G12_ROOT:-} ]] || lab_die 'Run ordinary-user bash scripts/run-g12-review.sh first (G12_ROOT required)'
root=$(realpath -e -- "$G12_ROOT")
[[ $root == "$repo"/results/p12-g12-* && -f $root/software.json && -d $root/fresh ]] || lab_die 'G12_ROOT must name a prepared fresh reproduction under results/'
[[ $(stat -c '%u' "$root") == "$SUDO_UID" ]] || lab_die 'G12 root belongs to a different owner'
if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER || -L $LAB_MARKER ]]; then
 lab_die 'stop foreground server and clean owned topology before full G12'
fi
run_user() { setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups --reset-env -- env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C "$@"; }
# Validate the source export again before the privileged network actions.
run_user python3 tests/system/check_g12.py "$root" --software
[[ -f $root/rehearsal.json ]] || lab_die 'Run the offline walkthrough from ordinary-user scripts/run-g12-review.sh first'
# Demos are public Make commands invoked by the ordinary user in the original
# terminal. Avoid nesting another sudo authentication session inside this root
# wrapper. Each demo alone owns its privileged network/capture lifecycle.
if namespace_exists qclient || namespace_exists qserver || [[ -e $LAB_MARKER || -L $LAB_MARKER ]]; then lab_die 'G12 namespace/marker remains'; fi
run_user python3 "$root/fresh/tests/system/check_g12.py" "$root"
printf 'G12: gate_root=%s status=PASS\n' "$root"
