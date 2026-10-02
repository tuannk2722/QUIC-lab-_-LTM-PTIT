# P10/G10 — implementation/software PASS, actual IFB BLOCKED

Thu dữ liệu ngày2026-10-01 UTC; hoàn thiện hồ sơ sau resume ngày2026-10-02. Ubuntu26.04.1/WSL2, application/tests/analysis UID1000. User xác nhận P9/G09 PASS và cho phép riêng P10. Agent dừng để human review P10; không commit hoặc mở P11/P12. Không tự nhận đã human-review code hoặc rerun privileged G09 của bản sửa D24.

**Overall G10 BLOCKED:** full attempt `sudo -n bash tests/system/run.sh --gate G10` exit1 trước runner, `sudo: interactive authentication is required` ([log](g10-system-attempt.log)). Không topology mutation, không actual P10 ingress IFB dataset. Full localhost cohort/plots chỉ correctness. API qualification chưa là packet0RTT proof; qlog/PCAP/progress thuộc P11.

Thử lại sau resume vẫn exit1 trước runner với cùng lỗi ([resume attempt](g10-system-resume-attempt.log)); không là automatic approval rejection. Final build receipt [log](g10-build-final.log), full analysis19 tests [log](g10-analysis-complete.log), checker4 mutations [log](g10-checker-final.log), static/gofmt/shell/Python/build-receipt checks [JSON](g10-static.json) đều PASS. Pure kernel/probe/host helper đọc lại512 snapshots/bốn probes của historical G09 và idle/chronology256 entries ([kernel](g10-archived-network-check.log), [idle](g10-idle-compatibility.log)); đây là parser compatibility, không actual G10 traffic. Visual review của total_ms.png thấy đủ units/counts/mode achievement/P11 disclaimer, không clipping.

## Behavior và flow cần review

Client và bench cùng RunTrial/RunSession. Cold dùng TLS clone/cache rỗng. Resumed/early mỗi sequence có cache mới, mở prior cold connection cùng process rồi chờ non-nil cache Put bằng notification/deadline, không sleep. Prior connection có t0 và canonical `ticket-warmup/` riêng. Target t0 bắt đầu sau preparation: resumed dùng Dial, early dùng DialEarly. Observer ghi handshake khi client quan sát và join trước state read; actual DidResume/Used0RTT lấy từ connection, không hardcode.

Khi Err0RTTRejected, coordinator chờ tất cả workers dừng, snapshot attempt0 rồi NextConnection một lần. Với pinned quic-go, transition giữ cùng connection; replay toàn read-only batch bằng buffers/streams mới với original t0/deadline. Không cancel rejected streams đã invalidated vì IDs sẽ được reset/reuse. Final bytes/hash chỉ tính attempt cuối, history giữ original failure/timing/bytes. Forced-rejection test dùng valid fixed ticket keys, acceptance hook đổi true→false sau prior connection; sáu workers kiểm one replay, two connections và12 server REQUESTs (6 prior+6 replay), final6144 bytes/six hashes.

Default handshake suite: QUIC cold/resumed/early, profile1×1024/chunk1024, rtt50-loss0 (25ms mỗi hướng,20Mbps,0loss).96 targets =90 measured+6 phase warmups;64 prior ticket warmups ngoài aggregate. Six-permutation cycle,10 measured samples/mode/vị trí, shared seed/triple và seed mới giữa triples. Wrapper reset/inspect trước mỗi sequence khi idle; condition giữ qua prior+target. Watchdog2×timeout+15s, target timeout xuyên replay. Short1KiB không dùng bulk downstream5×upstream/sustained-goodput sanity; actual config/placement/filter/offload/RTT/counters/identity/cleanup vẫn bắt buộc.

Transfer success và mode achievement được báo riêng. Accepted early API qualification cần DidResume/Used0RTT=true, actual attempt, rejection=false, fallback0 và RequestEnd<observed Handshake. Successful fallback hoặc chưa đạt mode vẫn nằm denominator, không vào mode latency distribution. `n_mode_achieved`, `n_fallback`, `n_unachieved` đi cùng success/failures/n_values. P9 columns/cohort giữ nguyên.

## Gate evidence

| Acceptance / check | Status | Evidence thực |
|---|---|---|
| G10-build/suite/race | PASS | [build](g10-build.log), [suite verified](g10-suite-verified.log), [race verified](g10-race-verified.log) |
| G10-ticket/cold/resumed/accepted | PASS, localhost |7 canonical functional cases trong archive/review; cache notification/deadline/unit và real sockets |
| G10-rejected/one-replay/no-duplicate | PASS, localhost |Valid-ticket rejection: DidResume=true, Used=false, rejected=true, fallback1, attempt0/1 same t0;6144 final bytes |
| G10-missing-ticket/handshake-failure/cancel | PASS, localhost |Bounded failures, no replay; missing ticket no target invocation; unobserved TLS/Used state null |
| G10-default schedule/cohort/stats/plots | PASS, localhost |96 invoked/96 success/0fail/96 streams,90 measured+6 warmups;64 separate tickets; measured API-qualified cold30/resumed30/early29; early1 unachieved retained/excluded latency |
| G10-failure denominator | PASS, localhost |Wrong hostname3 targets/3fail/3 streams retained; no success-only filtering |
| G10-checker/analysis/network regression | PASS, software |[analysis log](g10-analysis.log), [network regression9](g10-network-regression.log); checker final recheck/mutations/static in status/review |
| G10-actual IFB/RTT/90+6/UID/cleanup | BLOCKED |[sudo attempt](g10-system-attempt.log), exit1 before runner; nonroot runner exit3 [log](g10-nonroot.log) |
| G10 overall | BLOCKED |Actual impaired cohort còn thiếu; localhost không thay gate |
| G11-packet0RTT/HOL/qlog/PCAP/progress; G12 | NOT_RUN |Không được mở trong phase này |

Real source root: `results/p10-software-0dq12lsw/`, với `functional/` (cold,resumed,early,rejected,missing_ticket,target_handshake_failure,target_cancel), `success/`, `tls-failure/`, `client-{cold,resumed,early}/`. [Software log](g10-software.log) ghi commands/exit/UID/counts. [localhost-review.json](localhost-review.json) kiểm1213 as-run artifacts, final checker trên copy, tính lại độc lập15 run-summary và6 resource-summary groups từ CSV, full archive byte equality; [localhost-artifacts.tar.gz](localhost-artifacts.tar.gz) lưu bền toàn dataset/logs/config public CA/CSV/raw/attempts/plots, không private key. [g10-status.json](g10-status.json) giữ final command exits/acceptance và files changed.

Archive chứa as-run source-hashes/build receipts. Final checker hardening, Make test wiring và existing TCP test fixture refinement có thể khác source hashes lúc dataset được chạy; review JSON liệt kê chính xác differences. Không rewrite as-run evidence hoặc bổ sung receipt giả. Historical experiment ID prefix `bulk_` được giữ từ shared ID generator; schedule/manifest suite thực là handshake.

Failure history được giữ: sandbox socket EPERM ([log](g10-suite-sandbox.log)); first rejected attempt phát hiện cancel old stream reset IDs ([tests](g10-session-tests.log), [debug](g10-rejection-debug.log)), fixed session tests [PASS](g10-session-after-fix.log). Concurrent final suite gặp existing TCP test fixture remote reset do chưa consume TLS send-half EOF ([log](g10-suite-final.log)); fixture đã đọc EOF trước response, sequential final suite/race PASS. Không đổi production TCP. First-test log là partial diagnostic, không dùng làm final gate evidence.

## Tái lập trong Ubuntu WSL2

Từ repo root trên native Linux filesystem, dùng ordinary user:

```bash
make build
make test
make test-race
make test-network
make test-analysis
python3 tests/system/run_g10_software.py
```

Pinned toolchain/cache và plotting packages đã có local; fresh checkout theo README cài exact Go/dependencies và `make analysis-deps` bằng user. Chỉ `make certs` nếu cert chưa có; không force thay server identity đang dùng. Localhost driver tạo directory mới, không append/overwrite evidence đã lưu.

Full actual G10 cần topology/server cũ absent; wrapper tự quản server/netns/qdisc và cleanup. Chạy bằng terminal tương tác để sudo xác thực:

```bash
make build
set -o pipefail
sudo bash tests/system/run.sh --gate G10 2>&1 | tee docs/evidence/p10/g10-user-run.log
g10_status=${PIPESTATUS[0]}
printf 'g10_exit=%s\n' "$g10_status" | tee -a docs/evidence/p10/g10-user-run.log
```

Chỉ nếu kernel/tc không hỗ trợ seed và chủ động chấp nhận null-seed limitation, thay sudo command bằng `sudo env NETEM_SEED=none bash tests/system/run.sh --gate G10` với log riêng; không silently retry unseeded. G10 không cho repeat-count overrides. Exploratory benchmark riêng: `make benchmark-handshake RUNS=1 WARMUPS=0`; không thay default gate.

Review printed `gate_root=results/p10-g10-*`: functional7 cases, main96 targets/96 streams/64 ticket directories,96 completed journals/claims, build receipt/source hashes, four raw ping probes, verified kernel snapshots/counter/idle chronology, summary/plots, app UID>0 và cleanup0/equal host snapshots. Failed transfers có thể tồn tại nhưng phải báo và có actual qualified samples mỗi mode; missing/infrastructure errors chặn PASS. G10 summary scope chỉ P10 functional+network cohort, packet proof ghi P11 pending.

## Files changed và limitations

Core: `internal/tlsconfig/sessioncache{,_test}.go`, `internal/transport/{types.go,quic/{early.go,client.go,server.go}}`, `internal/metrics/result.go`, `internal/bench/{session.go,runner.go,schedule.go,handshake_test.go,manifest.go}` và `internal/cli/{cli.go,bench.go}`. Verification: integration `early_test.go`, EOF refinement `audit_test.go`; system `g10.sh/check_g10.py/run_g10_software.py/test_handshake.py/run.sh`. Orchestration: `Makefile`, `scripts/{bench.sh,bench-support.py}`. Analysis: `cohort/summarize/plot/test_stats/validate/test_session_state.py`. Docs: TASK, README/START_HERE/INDEX, D25/CLI/METRICS/NETWORK/PLAN/TRACEABILITY/VERSIONS/AI_USAGE/ACCEPTANCE_RESULTS và evidence này. Không đổi configs, schemas, Go/quic-go/plotting pins hoặc historical references/evidence.

Điểm review chính: worker join trước replay và không cancel old rejected streams; original t0/deadline/attempt-index/final byte accounting; observer latency/nullability/API state; ticket readiness vs preparation failure; triple order/seeds/network reset/short-payload policy; receipt/journal/raw/history/warmup binding; full denominator vs mode-eligible samples và p95/sample stddev. Actual IFB orchestration của P10 chưa verified. Shared WSL2 CPU/scheduling và observer scheduling ảnh hưởng timing; API state/Write return không chứng minh packet capture. Không có performance superiority/HOL causation claim, không 0ms response promise. Prior terminal Ctrl+C qua tee và fresh-boot IFB limitations trong P9/P7 vẫn cần review riêng; P10 không tự đóng chúng.
