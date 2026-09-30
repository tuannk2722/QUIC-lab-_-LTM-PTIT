#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
root=$(pwd)
case_dir=$(mktemp -d results/p6-g06-XXXXXX)
ready="$case_dir/ready.txt"
port=$(python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    print(sock.getsockname()[1])
PY
)
bin/server --transport=both --profile=bulk --listen="127.0.0.1:$port" --ready-file="$ready" >"$case_dir/server.log" 2>&1 &
server_pid=$!
cleanup() {
  kill -TERM "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT
for _ in {1..100}; do
  if [[ -s "$ready" ]]; then break; fi
  if ! kill -0 "$server_pid" 2>/dev/null; then cat "$case_dir/server.log" >&2; exit 1; fi
  sleep 0.05
done
[[ -s "$ready" ]] || { echo 'server readiness timeout' >&2; exit 1; }
line=$(cat "$ready")
[[ "$line" =~ tcp=([^[:space:]]+) ]] || exit 1
endpoint="${BASH_REMATCH[1]}"
bin/client --transport=tcp --mode=cold --profile=bulk --addr="$endpoint" --server-name=localhost --format=json --experiment-id=p6_g06 --run-id=tcp_success --out="$case_dir/tcp_success" >"$case_dir/tcp-success.json" 2>"$case_dir/tcp-success.stderr"
bin/client --transport=quic --mode=cold --profile=bulk --addr="$endpoint" --server-name=localhost --format=json --experiment-id=p6_g06 --run-id=quic_success --out="$case_dir/quic_success" >"$case_dir/quic-success.json" 2>"$case_dir/quic-success.stderr"
if bin/client --transport=tcp --mode=cold --profile=bulk --addr="$endpoint" --server-name=wrong.example --format=json --experiment-id=p6_g06 --run-id=tcp_failure --out="$case_dir/tcp_failure" >"$case_dir/tcp-failure.json" 2>"$case_dir/tcp-failure.stderr"; then
  echo 'negative trust test unexpectedly succeeded' >&2
  exit 1
fi
[[ ! -s "$case_dir/tcp-failure.json" ]] || { echo 'failed client emitted success stdout' >&2; exit 1; }
for trial in tcp_success quic_success tcp_failure; do
  python3 analysis/validate.py "$case_dir/$trial"
done
python3 analysis/test_validate.py "$case_dir"
python3 - "$case_dir" <<'PY'
import csv, sys
from pathlib import Path
root = Path(sys.argv[1])
def row(name):
    with (root/name/'runs.csv').open(newline='') as f:
        return next(csv.DictReader(f))
tcp, quic, fail = (row(x) for x in ('tcp_success', 'quic_success', 'tcp_failure'))
assert tcp['success'] == quic['success'] == 'true'
assert fail['success'] == 'false' and fail['error_code'] and fail['total_ms'] == ''
assert tcp['total_ms'] and quic['total_ms']
assert tcp['tcp_connect_ms'] and quic['tcp_connect_ms'] == ''
assert all(int(r['resource_count']) == 6 for r in (tcp, quic, fail))
assert tcp['bytes_received'] == quic['bytes_received'] == '6291456'
print(f'G06 actual trials: success=2 failed=1; retained failure={root}/tcp_failure; results={root}')
PY
echo "results_dir=$root/$case_dir"
