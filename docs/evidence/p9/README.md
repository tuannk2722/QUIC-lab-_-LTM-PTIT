# P9/G09 — actual user rerun PASS / dừng review

Lịch sử trước actual rerun (không là current status): ngày2026-10-01. User xác nhận P8/G08 PASS, cho phép riêng P9/G09 và yêu cầu dừng review. Code/software checks PASS; full G09 attempt ngoài sandbox exit1 **trước runner**: `sudo: interactive authentication is required`. Không có actual G09 gate_root/main240+16 dataset, RTT/counters/namespace interruption/cleanup của P9. G10–G12 chưa chạy. Không coi các plots localhost dưới đây là so sánh hiệu năng mạng.

## Actual closure 2026-10-01

User full G09 rerun 2026-10-01 tại results/p9-g09-8dFdkj PASS (g09_exit=0): main256 invoked/256 success/0 failure/0 missing, 240 measured+16 warmup/1536 resource rows; controlled SIGINT child130/cleanup0. Agent read-only audit/hash tại docs/evidence/p9/g09-rerun-review.json; không tự nhận chạy sudo. Dừng human review P9, không P10. Interactive terminal Ctrl+C qua tee từng exit141/cleanup1 vẫn là issue riêng, không được coi đã sửa bởi controlled child PASS.

Log: [g09-system-run2.log](g09-system-run2.log). [Review/hash](g09-rerun-review.json) verified3695 files; full actual [archive](g09-user-run-artifacts.tar.gz) ~4MiB byte-verified against all hashes. Source results/p9-g09-8dFdkj/ giữ nguyên. Runtime ~72.76 phút.

- Main: 256/256 success; 240 measured+16 warmup;1536 successful hash/resource rows; 1.5GiB useful payload.
- Kernel1286 snapshots được kiểm placement/filter/offloads/seed/units;256 before-after counter checks và256 accepted quiet samples. Hai transient idle retries trong log không là failed trial: subsequent saved samples quiet.
- Four probes12 samples/mỗi chiều: baseline medians0.3725/0.2685ms; rtt5050.85/50.55ms. Actual cold TLS1.3/ALPN/no resumption, QUICv1/no0RTT và client socket buffers; TCP kernel CC cubic, QUIC pinned Reno.
- Controlled interrupt:2 planned/1invoked/0success/2fail,12 resource rows; raw source stopped trial được aggregate demote environment_error vì thiếu post-network check, còn trial kia not_started; original130/cleanup0 là expected.
- Host snapshots trước/active/final byte-equal cả main/child; outside-sandbox ps không còn managed apps/wrapper, namespace paths absent.
- Tính lại độc lập40 summary rows +96 resource-summary rows (30 values/group, median/p95/sample stddev); inspected total_ms PNG axes/labels/allpoints. Saved3692 artifact hashes của checker vẫn match; thêm child/main checker và gate-summary thành3695 archive files.
- `summary.json.main_checked=false` là generic summarize invocation, không main failure; full `load(main=True)`/G09 checker đã riêng validate240+16/1536/defaults.

Lịch sử initial sudo block dưới đây giữ nguyên để provenance. Full gate đã PASS nên không cần rerun hiện tại. Đường interactive terminal Ctrl+C qua tee của lần results/p9-g09-qvyXOw main từng exit141/cleanup1/thiếu summary vẫn chưa sửa, không coi controlled child PASS là chứng minh đường terminal đó.

## Behavior/flow

1. Plan mới: config defaults30+2/transport/scenario, bốn main scenarios. Schedule v1/entries immutable và hash-bound với config/CA/endpoint/timeout; 256 entries, phase riêng, balanced AB/BA và unique seed/pair. Max4096 entries/8MiB; không shell eval.
2. Wrapper setup owned topology, RTT no-loss probes và managed server TCP+UDP4433. Go/checks/analysis/output đều UID thường; root chỉ network/namespace entry và process lifecycle. Reset/apply/verify trước TỪNG transport, cùng configured seed trong pair; actual snapshot phải khớp entry và qclient identity.
3. Cold trial dùng cùng RunCold với client, một fresh connection. N resource rows kể cả failure. Sidecar actual TLS/ALPN/cipher/QUIC state/client socket buffers lấy trong cleanup sau FIN, không đổi canonical schema/timing formulas. Watchdog timeout+15s/TERM/grace5s; infra/missing/incomplete dừng cohort, transfer failure có raw vẫn được giữ.
4. Inspect/check after, queues drain và quiet counters trước reset tiếp; failed transfer đợi full server deadline. Trap giữ130/143 và nonzero, dừng managed PID, clear/teardown, compare host link/address/route.
5. Merge một lần, giữ source/hash. Entry chưa chạy/thiếu/incomplete có failed representation và đủ N rows. `n_attempted` full scheduled denominator, `n_invoked` riêng. Missing elapsed=0 là unobserved sentinel (schema v1 non-nullable), latency/goodput/hash null; không đưa vào latency stats. Network verification thiếu/fail làm aggregate environment_error.
6. Validate/cohort → summary/resource-summary/report → points/box PNG/SVG. Successful measured latency; warmups excluded, failures/timeouts luôn báo, không bỏ outliers; p95 nearest-rank, sample stddev n−1/null dưới2. Resource distributions tách ID, không pooling sáu correlated resources thành independent trials.

## Verification thực

| Check | Command / exit | Evidence |
|---|---|---|
| Build | `make build`, 0 | g09-build.log |
| Full Go suite | `make test`, 0, UID1000 ngoài sandbox | g09-suite.log |
| Full race | `make test-race`, 0, UID1000 ngoài sandbox | g09-race.log |
| Stats + P9 network/idle checker units | `make test-analysis`, 0, 2 stats +2 checker tests/subcases | g09-stats.log |
| P8 network regression | `make test-network`, 0, 9 tests | g09-network-regression.log |
| Actual software CLI | `python3 tests/system/run_g09_software.py`, 0, UID1000 | g09-software.log; g09-software-review.json |
| Nonroot actual runner | `bash tests/system/run.sh --gate G09`, expected3 | g09-nonroot.log |
| Full actual G09 attempt | `sudo -n bash tests/system/run.sh --gate G09`, 1 trước runner | g09-system-attempt.log |
| Shell/Python/gofmt/diff hygiene | verified0 | g09-static.json |
| Make target wiring | `make -n benchmark analyze RESULTS=results/example`, 0 | g09-make-dry-run.log |

Go tests kiểm deterministic/default counts/AB–BA/seeds/bounds; changed entry/actual config refusal; missing/incomplete/foreign cohort/no overwrite; three fresh QUIC connections với actual cold state; actual blackhole TCP/QUIC timeout/cancel giữ failure slots. Không dùng synthetic unit clocks/counters làm measured dataset.

Software result root thực: `results/p9-software-6011935o/`:

- success/: 6 invoked/6 success/0 failure, 4 measured +2 warmups, 36 resource rows.
- tls-failure/: 2 invoked/0 success/2 TLS identity failures, 12 resource rows.
- interrupted/: 4 scheduled/2 invoked, 1 success/3 failure, 24 resource rows: một process SIGKILL thật trước output, hai entry chưa chạy. Source invocation/cause và missing diagnostics giữ riêng.
- default-plan/: 256 entries được tạo, **chưa execute**, không runs.csv. Không fake main dataset.

Bản lưu bền: [actual/](actual/) giữ đầy đủ ba software cases; default-plan chỉ lưu schedule/manifest/config/source hashes. [archive-provenance.json](archive-provenance.json) đối chiếu140 archived files byte-for-byte với source/hash. Original review chứa cả source entry hashes/logs. g09-software-first.log giữ successful lượt trước refinement journal/provenance tại results/p9-software-yo27jxcr; sandbox suite EPERM giữ g09-suite-sandbox.log, đã có final suite/race PASS ngoài sandbox. Installation thật bằng user ở g09-analysis-install.log; full Python dependency versions ở analysis/requirements.txt. Original configs/result schema/Go/quic-go/original references giữ nguyên.

## Full manual G09 command — terminal Ubuntu WSL2

Repo root native `/home/...`, topology/server cũ absent. Build/dependencies/cert dùng user thường. Hiện deps đã cài; fresh checkout mới cần analysis-deps. Không sudo build/pip.

```bash
make build
# Chỉ cần nếu .tools/analysis chưa có đúng pinned packages:
make analysis-deps
test -r certs/server.crt && test -r certs/server.key || make certs
set -o pipefail
sudo bash tests/system/run.sh --gate G09 2>&1 | tee docs/evidence/p9/g09-system.log
g09_status=${PIPESTATUS[0]}; printf 'g09_exit=%s\n' "$g09_status" | tee -a docs/evidence/p9/g09-system.log
```

Nhập sudo password trong terminal của bạn. Runner in `gate_root=results/p9-g09-...`, có `interrupt/` và `main/`. Full checker cần main256 invocations/240 measured+16 warmups/1536 resource rows, actual four RTT probes/network validity/TLS/manifest, cleanup0/unchanged host; child interrupt130 và reconstructed failed rows. Failed transfers được báo, không đặt numeric superiority gate; infra/missing/cleanup failure trong main không PASS. Chạy trên host rảnh, tránh thay qdisc/mạng lab đồng thời.

Seed unsupported: diagnose trước. Nếu chủ động chọn null limitation, dùng log riêng:

```bash
set -o pipefail
sudo env NETEM_SEED=none bash tests/system/run.sh --gate G09 2>&1 | tee docs/evidence/p9/g09-system-seed-none.log
g09_status=${PIPESTATUS[0]}; printf 'g09_exit=%s\n' "$g09_status" | tee -a docs/evidence/p9/g09-system-seed-none.log
```

Run independently: `make benchmark`, hoặc `sudo bash scripts/bench.sh --out=results/NEW_DIR`. Counts overrides/subsets là exploratory; `make analyze RESULTS=DIR` validate rồi regenerate derived files, giữ raw. Không merge lại aggregate đã có; nếu merge fail giữ INCOMPLETE để diagnose, recovery phải dùng fresh copy/destination và giữ original evidence. Full G09 hiện PASS sau actual user-run và agent artifact review; commands giữ để reproduction, không cần rerun dư thừa. Dừng P9 human review.

## Files changed

- New core: internal/bench/{schedule,runner,merge,manifest,bench_test}.go, internal/cli/bench.go, internal/transport/connection.go.
- Updated core: config/config.go (reuse bounded decoder/validation), cli/{cli,cli_test}.go, metrics/csv.go (single-owner aggregate), transport/{types,tcp/client,quic/client}.go (post-FIN observation).
- New tooling: scripts/bench.sh, bench-support.py; analysis/{cohort,summarize,plot,test_stats}.py và requirements.txt; tests/integration/bench_test.go; tests/system/{g09.sh,check_g09.py,run_g09_software.py,test_bench.py}.
- Updated wiring: Makefile, tests/system/run.sh. Docs/task: README, START_HERE, INDEX, CLI, METRICS, NETWORK, PLAN, CONTEXT D23, TRACEABILITY, VERSIONS, AI_USAGE, REPORT, ACCEPTANCE_RESULTS, TASK, evidence/p9.
- Không commit; không sửa dependency Go, config JSON, result schema hoặc references/originals.

## Review và limitation

Review schedule recomputation/hash/config/CA binding, AB–BA/seed reset và warmup separation; shared trial path/cancel/deadline/no duplicate; wrapper PID/UID/trap/host state và quiet-path policy; missing-row sentinel/n_invoked/full denominator/source provenance; network failures không lọt vào successful latency; p95/sample stddev/resource correlation và plots labels.

Actual main orchestration/counters/cleanup và controlled child P9 đã verified. Interactive Ctrl+C qua tee trước đó141/cleanup1 vẫn chưa sửa/kiểm lại. Historical sudo block giữ log. Snapshot không continuous lock, quiet counter sample không chứng minh không có mọi control packet tương lai; SIGKILL wrapper không trap. Server socket buffers/Windows WSL CLI version chưa đo, manifest ghi unknown/reason; client buffers/TLS có sidecar thật. WSL2 shared kernel/CPU, transport implementations/scheduling/CC khác nhau, paired seed không identical loss trace; downstream includes control/ACK, drops có thể overflow. Performance cohort30 measured/group đã thu, vẫn nhỏ; P10 early/resumption và P11 qlog/PCAP/progress/HOL causal proof pending.
