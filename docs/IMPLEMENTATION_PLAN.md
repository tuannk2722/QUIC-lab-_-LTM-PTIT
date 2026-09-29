# Implementation plan — theo phase và file

## Quy tắc thực hiện

Đọc đầy đủ docs trước P0. Gói này chỉ có docs/config/schema; không có hidden implementation để giả định. Thư mục code cần tạo nằm trong bản đồ dưới. Nếu đã có repo code, inventory/diff trước, bảo toàn thay đổi người dùng, không thay root AGENTS hiện có mà chưa đối chiếu nội dung. Không tự init/force-push/merge GitHub repo ngoài phạm vi; có thể làm local code và git diff.

Mỗi phase: đọc hợp đồng → inspect code → implement → chạy gate thực sự → sửa lỗi → cập nhật TASK. Pass thì tự tiếp tục; blocked environment thì làm phần độc lập, không hạ tiêu chí. Các phase P0–P12 đều thuộc mục tiêu cuối, không gọi P4 là hoàn tất.

## Bản đồ file cuối cùng

| Đường dẫn | Trách nhiệm | Phase |
|---|---|---|
| go.mod, go.sum | Khóa module/toolchain/dependencies thực | P0 |
| cmd/server/main.go | Parse flags, dependencies, lifecycle | P0/P2/P4 |
| cmd/client/main.go | CLI trial, formatting, exit codes | P0/P2/P5 |
| cmd/bench/main.go | Schedule/entry/merge CLI | P0/P9 |
| internal/config/config.go | Profiles/scenarios/limits/defaults, validation | P0 |
| internal/workload/resource.go, generator.go | Store immutable + deterministic data/hash | P1 |
| internal/protocol/frame.go, request.go, codec.go, errors.go | QB01 wire contract | P2 |
| internal/protocol/batch.go | Batch validation/barrier, transport-independent | P3/P4 |
| internal/transport/types.go | Trial input/output contracts, không abstraction quá mức | P2 |
| internal/transport/tcp/client.go, server.go, scheduler.go | TLS multiplex transfer | P2/P3 |
| internal/transport/quic/client.go, server.go, streams.go | Native stream transfer | P4 |
| internal/transport/quic/early.go | Ticket warm-up, early/reject/retry coordinator | P10 |
| internal/tlsconfig/client.go, server.go | Trust/SAN/ALPN/TLS1.3 | P0/P2 |
| internal/tlsconfig/sessioncache.go | Thread-safe cache + ticket signal | P10 |
| internal/metrics/timer.go, result.go, csv.go, json.go | Monotonic record, export, null/errors | P5/P6 |
| internal/metrics/progress.go | Evidence in-memory event collection | P11 |
| internal/bench/runner.go, schedule.go, merge.go | Fresh trials, seeds/order, failure rows | P9 |
| internal/observability/qlog.go, keylog.go | Optional traces và mapping, flush | P11 |
| scripts/gen-cert.sh | Local cert/key SAN, secure file permissions | P0 |
| scripts/doctor.sh | Read-only preflight + scoped disposable probe nếu cần | P0/P7/P8 |
| scripts/run-in-netns.sh | Privileged entry → user UID/GID | P7 |
| scripts/network/setup.sh, teardown.sh | Owned topology, rollback partial setup | P7 |
| scripts/network/netem.sh, clear-netem.sh, inspect.sh | Apply profiles, verify actual state | P8 |
| scripts/bench.sh | Privileged network orchestration around unprivileged bench | P9 |
| scripts/capture.sh, demo.sh | Evidence capture và managed live lifecycle | P11/P12 |
| analysis/validate.py, summarize.py, plot.py | Results contract, stats, charts | P6/P9/P12 |
| analysis/requirements.txt | Pin thư viện plotting nếu dùng ngoài stdlib | P9 |
| tests/integration/*_test.go | Transport/TLS/error/early functional tests | P2–P10 |
| tests/system/run.sh | Namespace/impairment/cleanup acceptance | P7–P12 |
| Makefile | Targets công khai đã mô tả | P0–P12 |
| docs/REPORT.md | Report template → kết quả thật và giới hạn | P9/P12 |
| docs/ACCEPTANCE_RESULTS.md | PASS/FAIL/BLOCKED + evidence từng gate | Mọi phase |

Unit tests cùng package: *_test.go theo chức năng cần kiểm, không một file monolithic. Tên file nội bộ có thể điều chỉnh nếu trách nhiệm giữ nguyên; update bảng này. Không xóa/re-export file nào trong gói ban đầu; Go không cần re-export wrapper. Bản gốc references chỉ đọc, giữ checksum. Thay đổi schema phải có version/migration rõ, không đổi tên cột ngầm.

## P0 — Toolchain, skeleton và TLS assets

Đọc: tất cả docs, sau đó VERSIONS/CLI/DEMO_SPEC. Kiểm Ubuntu VM thật; record OS/kernel/Go/quic-go compatibility. Chọn một stable tag phù hợp, go mod init với module local `quic-performance-lab` nếu chưa có remote module; pin version cụ thể và checksums. Dùng source/go doc đúng tag, không copy pseudo-code cũ.

Tạo config loader, ba mains parse help/version (chưa transfer phải báo not implemented/nonzero, không fake success), Makefile build/test/certs/doctor, cert script, version report. Không dùng `@latest` trong lệnh tái lập cuối.

Gate G00: build skeleton được; versions pinned; help/config rejects invalid input; cert SAN/trust check. G00 chưa chứng minh network functionality. Cập nhật VERSIONS từ `UNRESOLVED` thành verified với command/evidence.

## P1 — Workload

Tạo store/generator cho 6×1MiB, profile handshake, precomputed SHA256, client expectation. Byte rules và limits theo DEMO_SPEC. Store chung cho listeners, immutable; không filesystem IO trong measured data path.

Gate G01: cùng ID/offset cho cùng bytes/hash giữa lần generate; khác transport dùng cùng store; size/count overflow bị chặn; test fixture known small resource.

## P2 — QB01 và TCP/TLS một resource

Implement complete header/codec/META/DATA/FIN/ERROR, partial read/write, bounds, trust/ALPN/TLS1.3, timeout/cancel; TCP server/client 1 resource trước. Timing interface được định hình ngay nhưng chưa cần CSV hoàn chỉnh.

Gate G02: localhost thật truyền 1 resource đúng hash; untrusted cert fail; truncated frame/bad length/timeout không treo; parser tests và fuzz seed cases. Chưa dùng localhost đo hiệu năng.

## P3 — TCP multiplex đầy đủ

Implement request batch + deterministic round-robin scheduler 6 resources; single writer; client demux. Tách data store/framing/scheduling khỏi main. Enforce one connection per trial, record connection count trong integration instrumentation.

Gate G03: 6 resources hoàn tất hash trên 1 TLS connection; test transcript có DATA interleaved; no races khi cancel hoặc batch timeout; không `Write` resource toàn bộ trước resource kế tiếp.

## P4 — QUIC multiple streams

Implement quic-go server/client pin version; listeners cùng process/port number; same cert/store/QB01. Accept loop + stream workers + batch coordinator; real stream ID map; Close/Cancel đúng hướng. QUIC receive limits đủ ≥64 streams nếu max resource count64, và buffer credits được ghi config.

Gate G04: TCP+UDP cùng :4433; QUIC 1 connection/6 streams/6 checksum; stream count/map thật; simultaneous requests; invalid stream frame/cancel/EOF fail bounded; Go race app tests.

## P5 — Metrics

Place t0/tReq/tFirst/tPayloadDone/tDone/tHandshake hooks theo contract. Không timestamp first byte sau khi ReadFull xong 16KiB. Buffer/checksum prep trước t0; checksum verification sau tAll; metrics thread-safe và không heavy stdout.

Gate G05: synthetic clock/event tests kiểm công thức và nullability; integration mốc client hợp lệ; reqEnd không bị áp ordering giả; hash cost không nằm trong total_ms. Không dùng fake timings trong integration outputs.

## P6 — Results và validation

Implement JSON canonical, runs/streams fixed CSV headers, single owner writer/flush errors, progress contract reserve, unique IDs. Viết analysis/validate.py đối chiếu schema/FK/N rows/formulas/failures. Tạo docs/REPORT.md template có trạng thái chưa có số liệu.

Gate G06: actual successful + failed trial parse được; missing values rỗng; errors quoted đúng; no duplicate IDs; failure rows giữ lại; không đưa warmup vào measured summary.

## P7 — Namespace topology và privilege split

Implement setup/teardown/entry/ownership/readiness/cleanup. Chạy binary trong namespace với UID thường, resource port4433 không cần root. Add system checks for collision and partial failure. Không shell global trap kill unrelated process.

Gate G07: ping/connect qclient↔qserver, UDP/TCP transfers thật; setup/teardown hai lần; Ctrl+C không để orphan; host NIC/routes không đổi. Nếu quyền bị chặn: code/unit hoàn thành nhưng G07 BLOCKED.

## P8 — Impairment chính xác

Implement IFB ingress receiver path + egress-demo profile riêng, JSON scenarios, measured RTT/counters/offload/seed reports. Clear profile cũ trước apply profile mới. Inspect config thực và label profile mọi run.

Gate G08: rtt50-loss0 đo theo tolerance; counters direction đúng; server→client loss không tự gọi data-only; rate sanity; netem errors cause nonzero; clear/teardown after errors. Chỉ proceed cohort main khi ingress-ifb verified.

## P9 — Runner, benchmark và thống kê

Implement schedule plan/entry/merge, shell orchestrator, 30 trials/transport/scenario +2 warmups, balanced AB/BA, seed schedule, trial deadline và failures. Pin analysis dependencies. `analysis/summarize.py` đúng stats. Thu main performance dataset **thật** khi testbed sẵn sàng.

Gate G09: 240 measured +16 warmup raw rows cho suite mặc định; stream rows đầy đủ; interrupted/missing shard có failed representation; n_success+n_failed=n_attempted; same cohort config; CSV-derived charts/summary. Performance proof có thể chờ P11/P12 bổ sung nhưng raw đã đủ.

## P10 — Resumption và 0-RTT

Read exact pinned early APIs. Client cache wrapper có ticket notification; three modes trên handshake profile. Server accept early; verify state; per-run retry coordinator with bounded one replay read-only after rejection; preserve t0/attempt history.

Integration tests: cold no ticket, resumed without early, early accepted, deliberately rejected early with valid resumption setup, missing ticket timeout, handshake failure/cancel. Forced rejection test phải giữ ticket keys hợp lệ khi đổi acceptance (dùng config hook đúng version hoặc test harness có ticket keys cố định); không chỉ xóa cache rồi gọi đó là rejection.

Gate G10: actual Used0RTT+DidResume+timing/evidence sau P11; accepted and rejection correctness; no duplicate fallback; early rejected records false, fallback_count=1 và bytes correct. Run 3×30 handshake suite; warmups logged, không gộp vào bulk.

## P11 — qlog, PCAP, progress evidence

Implement optional observability, QLOGDIR/mapping, correct decoder, capture managed PID, keylog riêng, progress in-memory. Validate qvis hoặc giải pháp viewer phù hợp qlog version; thu sample UDP/QUIC, early packet, loss trace. Store all evidence attempts, chọn representative run có tiêu chí giải thích và disclose.

Gate G11: qlog parse/open thật; PCAP decode QUIC UDP; 0-RTT evidence corroborates API state; HOL trace đủ causal detail hoặc status inconclusive. Không gọi chứng minh HOL nếu chỉ có completion chart. Instrumented dataset tách khỏi main performance.

## P12 — Đóng gói end-to-end và rehearsal

Make targets demo/benchmark/analyze/cleanup hoạt động; update README/DEMO_SCRIPT bằng lệnh chạy thật, REPORT từ số liệu, AI_USAGE, ACCEPTANCE_RESULTS. Rehearse live 5–7 phút offline dependencies; screenshot/video backup gắn run_id thật nếu cần. Soát lý thuyết và quyền sở hữu code để nhóm có thể bảo vệ.

Gate G12: fresh checkout theo README build/run/cleanup được; tất cả mandatory acceptance có evidence; không có placeholder success, fabricated results hoặc TODO cốt lõi; final report còn blocked gì nói đúng. Slides được hỗ trợ bằng outline và assets thật; không coi deck là đã nộp hoặc tự upload db.ptit.edu.vn.

## Khi đổi phiên hoặc dừng giữa chừng

TASK lưu phase, exact next action, file read/changed, commands+exit/results, unresolved issues. Dùng trạng thái NOT_STARTED/IN_PROGRESS/PASS/FAIL/BLOCKED, không checkbox done cho phần chưa chạy. Khi resume, kiểm git diff và artifact tồn tại trước tin vào checkpoint. Không “làm lại từ đầu” vì context chat mất.
