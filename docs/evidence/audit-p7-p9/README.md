# Audit fixes P7–P9 — 2026-10-01

Scope: đúng năm findings được user cho phép; không P10, không thay protocol/config/schema/toolchain hoặc raw evidence lịch sử. Quyết định D24 trong CONTEXT_AND_DECISIONS.

| Acceptance / regression | Status | Bằng chứng |
|---|---|---|
| G00 build regression | PASS | build.log; Make tạo ba binaries và build receipt |
| G06/G09 journal + atomic claim | PASS software | bench-unit.log, go-suite.log, go-race.log; 32 concurrent claims chỉ một thắng; absent/unfinished/invalid journal không thành success |
| G07/G09 experiment exclusivity | PASS software | analysis.log, lifecycle-final.log; process cạnh tranh exit3, lock release khi owner kết thúc |
| G07/G09 SIGINT + closed stdout finalization | PASS software | lifecycle-final.log; production cleanup body, stdout đóng, expected trial exit130; cleanup0, đủ merge/summary/plots và original130 |
| G09 provenance | PASS software | Go/Python stale source/new source/replaced server/bench/self-image tests; actual verified descriptor exec trong localhost-review.json |
| G08 regression | PASS software | network-unit.log, 9 tests; không có kernel impairment mới |
| G09 actual localhost | PASS correctness | software.log, localhost-review.json, localhost-artifacts.tar.gz |
| G09 bản sửa: actual namespace/IFB/main/competing runner/interrupt | BLOCKED | system-attempt.log: sudo yêu cầu xác thực tương tác trước runner; chưa có actual network artifacts mới |

Lệnh đã chạy: `make build`, `make test`, `make test-race`, `make test-network`, `make test-analysis`, `python3 tests/system/test_audit_p7_p9.py -v`, `python3 tests/system/run_g09_software.py`. Go suite/race và localhost runner chạy UID1000 ngoài sandbox với socket permission hợp lệ. Không root build/app. Python/shell syntax, gofmt và diff hygiene kiểm riêng trong static.log. First localhost attempt vấp trùng tên log trong test (software-first-attempt.log); đã sửa test, final run exit0.

Actual localhost root: `results/p9-software-jf1ghox3/`. Success6 (4 measured+2 warmup), TLS failure2, interrupted4 (1 success+3 failed, gồm process SIGKILL và not_started). Tất cả rows/latencies ở archive là observations localhost; default plan256 chỉ planned. Thử entry trùng dùng TCP blackhole thật: invocation thứ nhất đã dial, invocation thứ hai exit1 mà không mở connection thứ hai. Verified-exec chạy binary qua descriptor đã hash. Archive giữ 440 source artifacts được hash-checked và toàn archive được byte-compare với thư mục nguồn; provenance/commands trong localhost-review.json. Không coi observations này là main performance data.

## Reproduction software

Từ repo root Ubuntu WSL2, dependencies/cert đã chuẩn bị bằng user:

```bash
make build
make test
make test-race
make test-network
make test-analysis
python3 tests/system/run_g09_software.py
```

`make build` là bắt buộc sau khi đổi Go app source, Makefile hoặc build helper. Giữ receipt cùng experiment; không sửa/xóa claim để replay entry. Merge cũ đã finalized không được ghi đè. Legacy analysis vẫn đọc evidence cũ; checker G09 mới yêu cầu build receipt và journal hoàn tất.

## Actual G09 còn cần chạy

PASS lịch sử tại `results/p9-g09-8dFdkj` giữ nguyên cho source cũ. Gate của bản sửa không kế thừa PASS đó. Khi topology cũ/server đã dừng, trong terminal Ubuntu:

```bash
make build
set -o pipefail
sudo bash tests/system/run.sh --gate G09 2>&1 | tee docs/evidence/audit-p7-p9/g09-user-run.log
g09_status=${PIPESTATUS[0]}
printf 'g09_exit=%s\n' "$g09_status" | tee -a docs/evidence/audit-p7-p9/g09-user-run.log
```

G09 mới kiểm runner cạnh tranh exit3 trong controlled interrupt case, child130/cleanup0, sau đó main240+16/1536 rows với receipt/journals/network/host checks. Không đổi impairment hoặc hạ tiêu chí khi capability bị chặn. Nếu seed không được kernel hỗ trợ, dùng explicit `sudo env NETEM_SEED=none bash tests/system/run.sh --gate G09` và lưu limitation như runbook P9.

Đường Ctrl+C terminal/process-group qua tee cần kiểm riêng, vì unit closed-pipe không thay actual namespace cleanup:

```bash
terminal_out="results/audit-p7-p9-terminal-$(date -u +%Y%m%dT%H%M%S)"
set -o pipefail
sudo bash scripts/bench.sh --runs=2 --warmups=0 --scenario=rtt50-loss3 --out="$terminal_out" 2>&1 | tee docs/evidence/audit-p7-p9/terminal-user-run.log
# Nhấn Ctrl+C một lần khi thấy P9: trial=...; chờ cleanup kết thúc.
terminal_status=${PIPESTATUS[0]}
printf 'terminal_exit=%s results=%s\n' "$terminal_status" "$terminal_out"
python3 analysis/validate.py "$terminal_out"
python3 - "$terminal_out" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
c = json.loads((root / 'cleanup.json').read_text())
assert c['original_exit'] == 130 and c['cleanup_exit'] == 0
assert all(c['host_unchanged'].values())
assert len(json.loads((root / 'plots/index.json').read_text())['files']) == 8
assert (root / 'summary.csv').is_file()
print('terminal cleanup/artifacts PASS')
PY
```

Các log finalize bền vững ở `logs/merge.log`, `validate.log`, `summarize.log`, `plot.log`, `teardown.log`, kể cả tee đã đóng. Chỉ cập nhật actual status sau khi có kết quả thật. SIGKILL wrapper không thể trap; khóa experiment chỉ ngăn runner cạnh tranh, không cho phép người vận hành thay mạng lab thủ công trong transfer. Không claim chống sửa artifacts ác ý hoặc có HOL/0-RTT evidence.
