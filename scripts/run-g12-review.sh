#!/usr/bin/env bash
# Ordinary-user entry: fresh offline source reproduction before privileged demos.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID != 0 ]] || { echo 'Run as your ordinary Ubuntu WSL user.' >&2; exit 3; }
[[ $# == 0 ]] || { echo 'Usage: bash scripts/run-g12-review.sh' >&2; exit 2; }
g12_root="$PWD/results/p12-g12-$(python3 -c 'import secrets;print(secrets.token_hex(6))')"
mkdir -p docs/evidence/p12
g12_log=$(mktemp docs/evidence/p12/g12-user-run.XXXXXX.log)
set +e
python3 tests/system/run_g12_software.py --out "$g12_root" 2>&1 | tee "$g12_log"
pipeline_status=("${PIPESTATUS[@]}")
set -e
if (( pipeline_status[0] != 0 || pipeline_status[1] != 0 )); then
 printf 'g12_software_exit=%s\ngate_root=%s\nlog=%s\n' "${pipeline_status[0]}" "$g12_root" "$g12_log"
 exit 1
fi
sudo -v
backup="$PWD/results/p11-g11-6a8cc99602b7"
source scripts/process-lifecycle.sh
rehearsal_pid=
group_running() {
 ps -eo pgid=,stat= | awk -v managed_pg="$rehearsal_pid" '$1==managed_pg && $2 !~ /^[ZX]/ {found=1} END {exit !found}'
}
cleanup() {
 local original=$? stopped=0 forced=false poll
 trap - EXIT; trap '' INT TERM
 if [[ -n $rehearsal_pid ]]; then
  kill -TERM -- "-$rehearsal_pid" 2>/dev/null || kill -TERM "$rehearsal_pid" 2>/dev/null || true
  # The leader may finish first with130/143 while its demo descendants drain
  # captures. Wait for the owned process GROUP, not only the leader's status.
  for ((poll=0;poll<1200;poll++)); do group_running || break; sleep .05; done
  if group_running; then forced=true; kill -KILL -- "-$rehearsal_pid" 2>/dev/null || true; fi
  wait "$rehearsal_pid" || stopped=$?
  [[ $forced == false ]] || stopped=1
  (( original != 0 )) || original=$stopped
 fi
 exit "$original"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Keep the original terminal/session for tty-scoped sudo credentials. The
# child creates its own process group for bounded managed signal forwarding.
python3 "$g12_root/fresh/scripts/g12-rehearse.py" "$g12_root" "$backup" & rehearsal_pid=$!
rehearsal_status=0
wait "$rehearsal_pid" || rehearsal_status=$?
rehearsal_pid=
# Keep the preparation/live timeline in the public entry log as well as the
# dedicated receipt log, including unsuccessful timed rehearsals.
if [[ -f $g12_root/logs/walkthrough.log ]]; then
 cat "$g12_root/logs/walkthrough.log" >> "$g12_log"
fi
if (( rehearsal_status != 0 )); then
 printf 'g12_rehearsal_exit=%s\ngate_root=%s\nlog=%s\n' "$rehearsal_status" "$g12_root" "$g12_log" | tee -a "$g12_log"
 exit "$rehearsal_status"
fi
set +e
sudo env G12_ROOT="$g12_root" bash tests/system/run.sh --gate G12 2>&1 | tee -a "$g12_log"
pipeline_status=("${PIPESTATUS[@]}")
set -e
printf 'g12_exit=%s\ngate_root=%s\nlog=%s\n' "${pipeline_status[0]}" "$g12_root" "$g12_log" | tee -a "$g12_log"
(( pipeline_status[1] == 0 )) || { echo 'Evidence log write failed.' >&2; exit 1; }
exit "${pipeline_status[0]}"
