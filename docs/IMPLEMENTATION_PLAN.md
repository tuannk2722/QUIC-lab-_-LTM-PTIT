# Implementation plan — theo phase và file

## Quy tắc thực hiện

Mỗi phiên đọc AGENTS/INDEX/TASK và normative docs liên quan phase được cho phép; dùng originals khi ambiguity/conflict/provenance/final traceability. Gói này chỉ có docs/config/schema; không có hidden implementation để giả định. Thư mục code cần tạo nằm trong bản đồ dưới. Nếu đã có repo code, inventory/diff trước, bảo toàn thay đổi người dùng, không thay root AGENTS hiện có mà chưa đối chiếu nội dung. Không tự init/force-push/merge GitHub repo ngoài phạm vi; có thể làm local code và git diff.

Mỗi phase: đọc hợp đồng → inspect code → implement → chạy gate thực sự → sửa lỗi → cập nhật TASK. Mặc định HUMAN-GATED: chỉ phase/milestone user cho phép rõ ràng; sau gate và TASK thì dừng review. Chỉ tự nhiều phase/end-to-end khi user yêu cầu rõ ràng. Build riêng lẻ không đủ pass gate; blocked environment thì làm phần độc lập trong phạm vi được phép, không hạ tiêu chí. Các phase P0–P12 đều thuộc mục tiêu cuối, không gọi P4 là hoàn tất.

## Bản đồ file cuối cùng

| Đường dẫn | Trách nhiệm | Phase |
|---|---|---|
| go.mod, go.sum | Khóa module/toolchain/dependencies thực | P0 |
| cmd/server/main.go | Parse flags, dependencies, lifecycle | P0/P2/P4 |
| cmd/client/main.go | CLI trial, formatting, exit codes | P0/P2/P5 |
| cmd/bench/main.go | Schedule/entry/merge CLI | P0/P9 |
| internal/cli/cli.go | CLI skeleton/flags/exit/version dùng chung ba mains | P0 |
| tests/api/quic_test.go | Compile smoke của API đúng tag; không chạy QUIC | P0 |
| internal/config/config.go, json.go | Profiles/scenarios/limits/defaults, validation | P0 |
| internal/workload/resource.go, generator.go | Store immutable + deterministic data/hash | P1 |
| internal/protocol/frame.go, request.go, codec.go, errors.go | QB01 wire contract | P2 |
| internal/protocol/batch.go | Batch validation/barrier, transport-independent | P3/P4 |
| internal/transport/types.go | Trial input/output contracts, không abstraction quá mức | P2 |
| internal/transport/tcp/client.go, server.go, scheduler.go | TLS multiplex transfer | P2/P3 |
| internal/transport/quic/client.go, server.go, streams.go | Native stream transfer | P4 |
| internal/transport/quic/early.go | Ticket warm-up, early/reject/retry coordinator | P10 |
| internal/tlsconfig/config.go | Trust/SAN/ALPN/TLS1.3 chung; không mở socket ở P0 | P0/P2 |
| internal/tlsconfig/sessioncache.go | Thread-safe cache + ticket signal | P10 |
| internal/metrics/timer.go, result.go, csv.go, json.go | Monotonic record, export, null/errors | P5/P6 |
| internal/transport/progress.go, internal/metrics/progress.go | Bounded per-resource collector và post-timing CSV | P11 |
| internal/bench/runner.go, schedule.go, merge.go, manifest.go | Shared cold trials, immutable hash-bound seeds/order, failure rows, provenance/host metadata | P9 |
| internal/bench/session.go | Shared three-mode sequence; final, ticket warm-up và attempt artifacts | P10 |
| internal/cli/bench.go, internal/transport/connection.go | Bench flags/lifecycle, actual post-FIN TLS/socket sidecars | P9 |
| internal/observability/trace.go | Optional traces và mapping, flush | P11 |
| scripts/tls_keylog_overlay.py, run-g11-review.sh | Hash-checked build-only early keylog fix và ordinary-user G11 entry | P11/D28 |
| scripts/gen-cert.sh | Local cert/key SAN, secure file permissions | P0 |
| scripts/doctor.sh, preflight-network.sh | Inventory không root; primitive probe đặc quyền tách riêng, namespace tạm | P0/P7/P8 |
| scripts/run-in-netns.sh | Privileged entry → user UID/GID | P7 |
| scripts/network/setup.sh, teardown.sh | Owned topology, rollback partial setup | P7 |
| scripts/network/netem.sh, clear-netem.sh, inspect.sh, state.py | Apply/clear profiles, verify kernel/offload/seed actual state | P8 |
| internal/config/network.go | Read bounded recent network snapshot, check client namespace identity | P8 |
| tests/system/g08.sh, check_g08.py, test_network.py | G08 traffic gate/checker and unprivileged negative tests | P8 |
| scripts/bench.sh, bench-support.py | Privileged network orchestration; unprivileged checks/journals/metadata/analysis | P9 |
| scripts/capture.sh, process-lifecycle.sh, evidence-support.py, tshark.sh, prepare-decoder.py | Managed capture, child exit status, UID sinks/manifest và pinned offline decoder | P11 |
| scripts/demo.sh, demo-support.py | Managed live lifecycle, fixed sample plan, conservative packet/HOL audit và pre-recorded backup | P12 |
| scripts/run-g12-review.sh, tests/system/run_g12_software.py, check_g12.py | Ordinary-user fresh local checkout+candidate/offline reproduction và full Make-demo/rehearsal gate | P12 |
| analysis/validate.py, cohort.py, summarize.py, plot.py | Results/cohort contract, stats, charts | P6/P9/P12 |
| tests/system/g09.sh, check_g09.py, run_g09_software.py, test_bench.py | Actual default+interrupt gate; software localhost and checker unit regression | P9 |
| tests/system/g10.sh, check_g10.py, run_g10_software.py, test_handshake.py | G10 functional +96-target IFB gate, raw/ticket/history checks, localhost/pure regression | P10 |
| analysis/requirements.txt | Pin thư viện plotting nếu dùng ngoài stdlib | P9 |
| tests/integration/*_test.go | Transport/TLS/error/early functional tests | P2–P10 |
| tests/system/g11.sh, check_g11.py, run_g11_software.py | Actual evidence gate, archived checker và localhost correctness | P11 |
| analysis/evidence.py, packet_evidence.py, hol.py, decoder-packages.json | quic-12 viewer/correlation, tshark PDML, causal criteria và decoder pin | P11 |
| tests/system/run.sh | Namespace/impairment/cleanup acceptance | P7–P12 |
| Makefile | Targets công khai đã mô tả | P0–P12 |
| docs/REPORT.md | Report template → kết quả thật và giới hạn | P9/P12 |
| docs/ACCEPTANCE_RESULTS.md | PASS/FAIL/BLOCKED + evidence từng gate | Mọi phase |

Unit tests cùng package: *_test.go theo chức năng cần kiểm, không một file monolithic. Tên file nội bộ có thể điều chỉnh nếu trách nhiệm giữ nguyên; update bảng này. Không xóa/re-export file nào trong gói ban đầu; Go không cần re-export wrapper. Bản gốc references chỉ đọc, giữ checksum. Thay đổi schema phải có version/migration rõ, không đổi tên cột ngầm.

## P0 — Toolchain, skeleton và TLS assets

Chỉ bắt đầu khi user cho phép P0 sau review migration. Đọc: AGENTS/INDEX/TASK, CONTEXT, VERSIONS/CLI/DEMO_SPEC, NETWORK§1, METRICS§5 và G00. Kiểm Ubuntu WSL2 thực; revalidate observations trong VERSIONS và record host OS/execution layer/distro/kernel/CPU/RAM/swap/WSL version, Go/quic-go compatibility. Capability preflight cũ không thay G07/G08. Chọn một stable tag phù hợp, go mod init với module local `quic-performance-lab` nếu chưa có remote module; pin version cụ thể và checksums. Dùng source/go doc đúng tag, không copy pseudo-code cũ.

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

Checkpoint lịch sử audit fix 2026-10-01 (D24): năm findings lifecycle/concurrency/provenance được user cho phép sửa trong P7–P9. Regression và evidence tại [audit-p7-p9](evidence/audit-p7-p9/README.md); actual G09 của bản sửa cần rerun, không kế thừa PASS của source cũ. Không mở P10.

Implement schedule plan/entry/merge, shell orchestrator, 30 trials/transport/scenario +2 warmups, balanced AB/BA, seed schedule, trial deadline và failures. Pin analysis dependencies. `analysis/summarize.py` đúng stats. Thu main performance dataset **thật** khi testbed sẵn sàng.

Gate G09: 240 measured +16 warmup raw rows cho suite mặc định; stream rows đầy đủ; interrupted/missing shard có failed representation; n_success+n_failed=n_attempted; same cohort config; CSV-derived charts/summary. Performance proof có thể chờ P11/P12 bổ sung nhưng raw đã đủ.

Checkpoint lịch sử P9 2026-10-01: code/software/build/suite/race và actual localhost runner success/TLS failure/SIGKILL reconstruction PASS; main plan256 entries chưa execute. Actual G09 attempt bị sudo authentication chặn trước runner, **BLOCKED**, chưa main raw240+16. D23 mô tả immutable plan/hash, bounded4096 entries, scheduled denominator/n_invoked riêng, elapsed0 unobserved sentinel và original shards retained. Full runner `sudo bash tests/system/run.sh --gate G09` có separate actual interrupt + main dataset/checker/cleanup. Evidence/manual commands: evidence/p9/README.md. Dừng review P9, không mở P10.


Closure lịch sử actual P9/G09: User full G09 rerun 2026-10-01 tại results/p9-g09-8dFdkj PASS (g09_exit=0): main256 invoked/256 success/0 failure/0 missing, 240 measured+16 warmup/1536 resource rows; controlled SIGINT child130/cleanup0. Agent read-only audit/hash tại docs/evidence/p9/g09-rerun-review.json; không tự nhận chạy sudo. Dừng human review P9, không P10. Interactive terminal Ctrl+C qua tee từng exit141/cleanup1 vẫn là issue riêng, không được coi đã sửa bởi controlled child PASS.

## P10 — Resumption và 0-RTT

Read exact pinned early APIs. Client cache wrapper có ticket notification; three modes trên handshake profile. Server accept early; verify state; per-run retry coordinator with bounded one replay read-only after rejection; preserve t0/attempt history.

Integration tests: cold no ticket, resumed without early, early accepted, deliberately rejected early with valid resumption setup, missing ticket timeout, handshake failure/cancel. Forced rejection test phải giữ ticket keys hợp lệ khi đổi acceptance (dùng config hook đúng version hoặc test harness có ticket keys cố định); không chỉ xóa cache rồi gọi đó là rejection.

Gate G10: actual Used0RTT+DidResume+timing/evidence sau P11; accepted and rejection correctness; no duplicate fallback; early rejected records false, fallback_count=1 và bytes correct. Run 3×30 handshake suite; warmups logged, không gộp vào bulk.

Checkpoint lịch sử P10 refinement D25: defaults96 targets (90 measured+6 phase warmups),64 separately logged ticket warmups; six-permutation order/seed triples. Shared CLI/bench sequence dùng cache notification, original target t0 qua one replay, actual state và attempt index. CSV-derived summary phân biệt transfer success/mode achievement/fallback; early qualification dùng RequestEnd<observed Handshake, packet proof pending P11. Full command `sudo bash tests/system/run.sh --gate G10` chạy functional tests và ingress IFB default cohort; localhost driver không thay network gate. Actual G10 user-run PASS tại results/p10-g10-cR1oR9; checker audit/archive1836 files tại [P10](evidence/p10/README.md). Historical sudo BLOCKED giữ nguyên. User authorize riêng P11/G11 ngày2026-10-02.

## P11 — qlog, PCAP, progress evidence

Implement optional observability, QLOGDIR/mapping, correct decoder, capture managed PID, keylog riêng, progress in-memory. Validate qvis hoặc giải pháp viewer phù hợp qlog version; thu sample UDP/QUIC, early packet, loss trace. Store all evidence attempts, chọn representative run có tiêu chí giải thích và disclose.

Gate G11: qlog parse/open thật; PCAP decode QUIC UDP; 0-RTT evidence corroborates API state; HOL trace đủ causal detail hoặc status inconclusive. Không gọi chứng minh HOL nếu chỉ có completion chart. Instrumented dataset tách khỏi main performance.

Checkpoint lịch sử P11/D26–D28 (đã superseded bởi closure bên dưới): client/server optional qlog/keylog, per-resource bounded progress, standalone quic-12 viewer/PNG/SVG, pinned tshark4.6.4 và managed paired capture. `tests/system/run.sh --gate G11` có23 planned trials, all attempts và conservative packet/HOL checker. Actual user-run FAIL sau5 successes; D27 sửa lifecycle/environment/capture. D28 thêm hash-checked Go build-only early keylog overlay, localhost actual export/full suite/race/provenance PASS; không đổi pins/custom crypto. Early decrypted-PCAP precheck chạy sau3 handshake trials trước20 bulk. Tại checkpoint này full network còn chờ sudo, P12 chưa được phép.

Checkpoint lịch sử P11/D29: user-run1200e3df1cf2 FAIL trước topology/trial0/23 do reset-env PATH thiếu sbin/sysctl. Owner PATH/preflight đã sửa, exact runtime/lifecycle9 PASS; tại thời điểm đó patched full23/PCAP/HOL vẫn pending.

Closure P11/G11 2026-10-02: user chạy `bash scripts/run-g11-review.sh`, `g11_exit=0`, actual root `results/p11-g11-6a8cc99602b7`.23 invoked/23 success/0 failure,123 resource hashes,30 qlogs,46 complete paired captures/drop0/cleanup0; actual early REQUEST PN0/stream0 và causal HOL cặp `loss_0_tcp`/`loss_0_quic` PASS. Four RTT probes, ingress IFB/idle/UID và host cleanup verified. [Audit/archive](evidence/p11/g11-rerun-review.json) giữ as-run receipts và một self-log hash exception đã giải thích; lịch sử FAIL/BLOCKED không bị rewrite. User xác nhận PASS và authorize riêng P12; đây không là xác nhận human code review.

## P12 — Đóng gói end-to-end và rehearsal

Make targets demo/benchmark/analyze/cleanup hoạt động; update README/DEMO_SCRIPT bằng lệnh chạy thật, REPORT từ số liệu, AI_USAGE, ACCEPTANCE_RESULTS. Rehearse live 5–7 phút offline dependencies; screenshot/video backup gắn run_id thật nếu cần. Soát lý thuyết và quyền sở hữu code để nhóm có thể bảo vệ.

Gate G12: fresh checkout theo README build/run/cleanup được; tất cả mandatory acceptance có evidence; không có placeholder success, fabricated results hoặc TODO cốt lõi; final report còn blocked gì nói đúng. Slides được hỗ trợ bằng outline và assets thật; không coi deck là đã nộp hoặc tự upload db.ptit.edu.vn.

D30: P12 tạo fresh local detached Git checkout của HEAD, overlay đúng tracked+nonignored current candidate/hashes, không tạo commit/push. Không kế thừa app binaries/cert/results hoặc build cache; disclose prepared pinned offline Go/module/analysis/decoder caches. Entry `bash scripts/run-g12-review.sh` chạy build/cert/doctor/tests/localhost correctness/analysis từ fresh candidate bằng user, sau đó mandatory baseline acceptance trước live clock và ba demos basic→loss→0rtt trên actual ingress IFB trong terminal walkthrough đo5–7 phút cùng cleanup (D31); kiểm độc lập cả bốn Make targets. `make gate-g12` gọi cùng entry. Demo plans cố định1 basic QUIC/2 baseline TCP+QUIC/2 loss TCP+QUIC/3 cold-resumed-early; mọi attempt giữ nguyên, no superiority gate. Một live loss pair có thể HOL INCONCLUSIVE; backup accepted G11 phải hiện label pre-recorded và actual run IDs. Software PASS hoặc dry-run targets không thay actual demos/rehearsal. Actual user G12 results/p12-g12-51c13b94f99b PASS/g12_exit0,live360.000794s,baseline preparation177.218539s riêng;14softwaresteps/610sourcefiles và all-four-demo8success/early/HOL/cleanup/fullcheckerPASS. Previous423sFAIL giữ lịch sử; D31 giữ300–420s và baseline receipt/chronology; permission blocker phải là BLOCKED với command thực.

## Khi đổi phiên hoặc dừng giữa chừng

TASK lưu phase, exact next action, file read/changed, commands+exit/results, unresolved issues. Dùng trạng thái NOT_STARTED/IN_PROGRESS/PASS/FAIL/BLOCKED, không checkbox done cho phần chưa chạy. Khi resume, kiểm git diff và artifact tồn tại trước tin vào checkpoint. Không “làm lại từ đầu” vì context chat mất.

TASK giữ một checkpoint hiện hành ngắn với links tới evidence và normative docs. Khi cần lưu toàn văn checkpoint cũ, chuyển nguyên văn vào `.codex/history/` và gắn link lịch sử; không nối toàn bộ phase history hoặc sao chép cả implementation plan/evidence vào TASK. Đây là quy ước continuity, không thay acceptance hoặc provenance.

P12 historical timing-fix checkpoint (superseded by closure below): user results/p12-g12-7807db3f7c56 software14/14/bốn demos/cleanup exit0, rehearsal423.01996559s FAIL; final checker không chạy. D31 fix baseline clock orchestration, patched actual rerun pending sudo; original FAIL/BLOCKED receipts retained. Prior results/p12-g12-18124ccd073d software14/14 PASS và sudo exit1 là checkpoint lịch sử. Exact user entry `bash scripts/run-g12-review.sh`; no next phase/commit. First packaging status-cell FAIL retained in p12 evidence.

D31 historical software verification checkpoint (superseded by closure below): patched fresh results/p12-g12-timing-20261002 software14/14 PASS,605sourcehashes,12demo+24G12 regressions,6localhost attempts/5success+1expectedTLSfailure,1028canonicalhashes unchanged. New actual system attempt exit1 before runner (sudo authentication); patched overall BLOCKED. Latest historical actual7807 FAIL423.01996559s, independent all-four-demo/8success/early/HOL/cleanup audit PASS; originals retained. [P12](evidence/p12/README.md).

Closure actual P12/G12 — 2026-10-03 (Asia/Saigon): user `bash scripts/run-g12-review.sh` tại results/p12-g12-51c13b94f99b `g12_exit=0`,fullcheckerPASS.14softwaresteps/610sourcehashes,8/8demo successes,live360.000793725s (300–420s),baseline preparation177.218538684s riêng trước live. Actualearly/HOL/probes/IFB/UID/cleanup0/hostunchanged PASS;independent read-only [closure audit](evidence/p12/g12-rerun-review.json), [public bundle](evidence/p12/g12-user-run-artifacts.tar.gz). Earlier423sFAIL/sudoBLOCKED retained;no raw/receipt/source rewrite, implementation unchanged. Dừng human review/codeownership/oraldelivery/slides;no commit/upload/nextphase.
