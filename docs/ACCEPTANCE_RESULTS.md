# Kết quả nghiệm thu — P0/G00 đến P12/G12

**Hiện hành (2026-10-03, Asia/Saigon): P0–P12/G00–G12 PASS.** User xác nhận G11 PASS và authorize riêng P12/G12. Actual G11 `results/p11-g11-6a8cc99602b7`, `g11_exit=0`:23/23 success,123 resource hashes, early REQUEST/HOL PASS, cleanup0/host unchanged; [audit/archive](evidence/p11/g11-rerun-review.json). Actual G12 results/p12-g12-51c13b94f99b g12_exit0/fullcheckerPASS:14softwaresteps/610sourcefiles,8/8successful demos,live360.000794s,baseline preparation177.218539s riêng,actualearly/HOL/cleanupPASS; [closure audit](evidence/p12/g12-rerun-review.json). Historical423sFAIL và sudoBLOCKED giữ nguyên; [P12 evidence](evidence/p12/README.md). Không commit/upload/nộp bài.

Ngày cập nhật: 2026-10-03 (Asia/Saigon; timestamps artifacts là UTC). Baseline: `7e54ad654b14b8eb38b0db369203df4d34f003d7`; đầu P4 ở commit `65d5a7b`. Người dùng đã human-review/approve P0/G00 và P4/G04; cho phép P5→G05→P6→G06 tuần tự. Môi trường: Ubuntu 26.04.1 LTS trong WSL2, UID 1000.

**Closure lịch sử P8/P9 (current status ở đầu tài liệu): P0/G00 đến P8/G08 PASS.** User chạy G08 rerun UTC02:57:20Z main exit0/cleanup0, tám successful bulk evidence trials/48 hashes, bốn RTT probes và expected SIGINT child130/cleanup0. Agent đối chiếu 35 verified snapshots, five clear snapshots, 15 equal host comparisons; [review/hash](evidence/p8/g08-rerun-review.json). Giữ failure/blocked logs lịch sử. User xác nhận P8 PASS và cho phép riêng P9. P9 code/software và full G09 actual user rerun PASS tại results/p9-g09-8dFdkj: main256 success/1536 rows, controlled child130/cleanup0; agent audit3695 hashes. Terminal Ctrl+C qua tee141/cleanup1 còn issue riêng; dừng human review P9, không P10. Chưa tự nhận human review code P9.

| ID / subcase | Trạng thái | Lệnh / cách kiểm | Kỳ vọng và kết quả thực | Evidence | Còn thiếu |
|---|---|---|---|---|---|
| G00-toolchain | PASS | SHA-256 archive; go version; go mod verify; go list -m all | Go 1.27.1, quic-go v0.63.0, minimum Go 1.26.0; all modules verified, exit 0 | [toolchain.json](evidence/p0/toolchain.json), [modules.txt](evidence/p0/modules.txt), [verify](evidence/p0/modules-verify.txt) | Không |
| G00-build | PASS | make build | Cả ba bin/server, bin/client, bin/bench build được; exit 0 | [commands](evidence/p0/g00-commands.log) | Chưa có transfer theo scope P0 |
| G00-help-version | PASS | Mỗi binary --help, --version | Exit 0; version ghi build/commit/dirty/Go/quic-go/QUIC | [commands](evidence/p0/g00-commands.log) | Không |
| G00-no-fake-success | PASS | Mỗi binary chạy input mặc định hợp lệ | Exit 1, not implemented; không mở listener hoặc tạo benchmark | [commands](evidence/p0/g00-commands.log), internal/cli/cli_test.go | Transport thuộc P2–P4 |
| G00-input-config | PASS | make test; CLI invalid transport/profiles | Exit 2 cho CLI input lỗi; tests reject unknown/duplicate/trailing/oversized JSON, bounds/overflow, timeout/mode/endpoint/count lỗi | [tests](evidence/p0/tests.log), [commands](evidence/p0/g00-commands.log) | Entry/shard validation thuộc P9 |
| G00-cert-SAN-trust | PASS | make certs; openssl verify; make test | SAN localhost/127.0.0.1/10.10.0.2 đều verify exit 0; hostname sai exit 2 như mong đợi; untrusted CA bị Go x509 reject | [commands](evidence/p0/g00-commands.log), [tests](evidence/p0/tests.log) | Chưa TLS transfer (G02) |
| G00-cert-policy | PASS | TLS/config tests, stat certs/server.key | TLS1.3/ALPN/trust đúng; key 0600; từ chối overwrite khi thiếu --force; explicit replacement có key/cert khớp | [tests](evidence/p0/tests.log), [commands](evidence/p0/g00-commands.log) | Không |
| G00-API-smoke | PASS | make test / tests/api | Compile API signatures Dial/Listen/stream/early/rejection/qlog và config fields đúng tag, exit 0; không chạy QUIC | [tests](evidence/p0/tests.log), [API notes](VERSIONS.md) | Runtime/evidence thuộc phase sau |
| G00-env-inventory | PASS ngoài sandbox | make doctor REPORT=docs/evidence/p0/doctor-host.txt | Exit 0; OS/kernel/CPU/RAM/swap/tools có evidence, Go process unprivileged | [doctor-host](evidence/p0/doctor-host.txt) | Host Windows/WSL app version vẫn user-reported, chưa truy vấn Windows CLI |
| G00-env-sandbox (lịch sử, đã có đường kiểm thay thế) | BLOCKED trong lần thử cũ | make doctor REPORT=docs/evidence/p0/doctor.txt | ip netns list bị netlink permission; doctor exit 3, Make exit 2. Đã rerun inventory ngoài sandbox đạt | [doctor-sandbox](evidence/p0/doctor.txt) | Giới hạn sandbox, không phải kernel thiếu module |
| G00-network-primitives | PASS | Người dùng: sudo bash scripts/preflight-network.sh | Log có netem 50ms, mirred redirect→ifb0 và PASS sau xóa namespace; người dùng xác nhận chạy thành công. Không có numeric exit code ghi riêng trong log | [probe](evidence/p0/network-probe.log), [provenance/hash](evidence/p0/network-probe-provenance.json) | Không; primitive probe không thay kết quả G07/G08 hiện tại |
| G01-fixture/determinism | PASS | `go test -v ./internal/workload` với local Go/cache | Fixture ID1 4 byte = `01 02 03 04`, SHA-256 cố định; bulk 6×1MiB và handshake 1×1KiB có cùng bytes/hash giữa hai lần generate | [tests](evidence/p1/g01-workload-tests.log), [manifest](evidence/p1/workload-manifest.json) | Không |
| G01-bounds/store | PASS | `make test`; `go test -race ./internal/workload` | Count/size/chunk/total overflow reject trước allocate; concurrent readers trên cùng immutable Store; toàn suite và race exit 0 | [suite](evidence/p1/g01-suite.log), [race](evidence/p1/g01-race.log) | Runtime TCP/QUIC chung store được kiểm ở G04 |
| G02-QB01 parser | PASS | `go test -v -count=1 ./internal/protocol` | Golden header 24 byte; REQUEST/META/ERROR roundtrip; partial read/write, coalesced frames, no-progress writer, malformed/truncated/oversize header, response state/hash; fuzz seed#0–2 đạt | [detailed tests](evidence/p2/g02-detailed-tests.log) | Không chạy long fuzz campaign; seed cases theo G02 |
| G02-TCP/TLS localhost | PASS | `make test`; `go test -v -count=1 ./tests/integration`; `make test-race` | TLS1.3/ALPN transfer 1×1024 byte đúng SHA-256; untrusted CA fail; truncated frame, bad length, timeout và cancel kết thúc hữu hạn; toàn suite/race exit 0 | [suite](evidence/p2/g02-suite.log), [detailed tests](evidence/p2/g02-detailed-tests.log), [race](evidence/p2/g02-race.log) | Localhost chỉ kiểm correctness |
| G02-CLI transfer | PASS | `make build`; `bin/server --transport=tcp --profile=handshake --listen=127.0.0.1:14433` + `bin/client` tương ứng; CA khác | Server ready; client exit 0 với 1024 byte/checksum true; CA khác exit 1/x509; server SIGTERM exit 0 | [build](evidence/p2/g02-build.log), [CLI](evidence/p2/g02-cli-transfer.log) | Canonical result files/metrics đầy đủ thuộc P5/P6 |
| G03-batch/scheduler | PASS | `go test -count=1 -v ./internal/protocol ./internal/transport/tcp` | Batch reject duplicate/count/chunk sai; transcript 6 resource có META 1..6, DATA xen vòng 0/2/4, FIN sau DATA cuối; không ghi trọn file theo ID | [detailed tests](evidence/p3/g03-detailed-tests.log) | Transcript là QB01 frame order, không suy ra TCP packet order |
| G03-TCP multiplex | PASS | `make test`; `go test -count=1 -v ./tests/integration`; `make test-race` | Localhost thực: 1 accepted TLS connection/6 resources ×1 MiB, đủ 6 hash; batch thiếu timeout có ERROR 6, duplicate ERROR 3, cancel giải phóng handler; suite/race exit 0 | [suite](evidence/p3/g03-suite.log), [detailed tests](evidence/p3/g03-detailed-tests.log), [race](evidence/p3/g03-race.log) | Localhost chỉ kiểm correctness; không phải benchmark |
| G03-CLI bulk | PASS | `make build`; `bin/server --transport=tcp --profile=bulk --listen=127.0.0.1:14435`; `bin/client --transport=tcp --profile=bulk --addr=127.0.0.1:14435 --server-name=localhost --format=json` | Ba binaries build exit 0; client/server exit 0; JSON 6 rows, 6,291,456 bytes, 6 checksum true; server SIGTERM exit 0 | [build](evidence/p3/g03-build.log), [CLI transfer](evidence/p3/g03-cli-transfer.log) | `elapsed_ms` ở stdout chỉ thông tin localhost; canonical results thuộc P5/P6 |
| G04-build/suite/race | PASS | `make build`; `make test`; `make test-race` | Ba binaries build; toàn suite app/integration và race đều exit 0 trong Ubuntu WSL2, UID 1000 | [build](evidence/p4/g04-build.log), [suite](evidence/p4/g04-suite.log), [race](evidence/p4/g04-race.log) | Không |
| G04-one-connection/stream-map | PASS | `go test -mod=readonly -count=1 -v -run '^TestQUIC' ./tests/integration` | 1 accepted QUIC connection, 6 native stream IDs khác nhau, server/client map khớp ID 1..6, 6×1 MiB và SHA-256 đúng; TCP cùng port/store cũng có 6 hash | [detailed tests](evidence/p4/g04-detailed-tests.log), [QUIC result](evidence/p4/quic-transfer.json), [TCP result](evidence/p4/tcp-transfer.json) | Loopback correctness, không phải performance |
| G04-batch/lifecycle/error | PASS | Cùng detailed test và `make test-race` | Barrier chờ đủ request; requests chạy đồng thời; missing/duplicate/invalid/truncated/non-EOF/extra stream đều kết thúc hữu hạn; server cancel giải phóng workers; client từ chối EOF trước FIN; CA không tin cậy bị x509 từ chối; race sạch | [detailed tests](evidence/p4/g04-detailed-tests.log), [race](evidence/p4/g04-race.log) | Không chạy long fuzz hay loss test trong G04 |
| G04-dual-listener CLI | PASS | `bin/server --transport=both --profile=bulk --listen=127.0.0.1:4433 --ready-file=<temp>`; `bin/client --transport=tcp|quic --mode=cold --profile=bulk --addr=127.0.0.1:4433 --server-name=localhost --format=json` | Một server process ready TCP+UDP cùng `:4433`, cùng certificate/store và limiter 8 trong code; hai client exit 0, 6 hash/6.291.456 bytes mỗi transport, QUIC JSON có 6 stream ID thật; server SIGTERM exit 0, ready file được gỡ | [CLI transfer](evidence/p4/g04-cli-transfer.log), [stream map/result](evidence/p4/quic-transfer.json), [TCP result](evidence/p4/tcp-transfer.json) | `elapsed_ms` trên localhost không dùng so sánh hiệu năng; CSV/metrics chuẩn thuộc P5/P6 |
| G05-formulas/nullability | PASS | `make build`; `make test`; `go test -mod=readonly -count=1 -v ./internal/metrics ./internal/protocol ./tests/integration` | Synthetic monotonic events đúng connect/handshake/TTFA/transfer/total/elapsed/goodput, missing mốc null; reqEnd sau firstByte hợp lệ; total loại hash/cleanup; TCP failure sau dial giữ tcp_connect mà handshake rỗng | [build](evidence/p5/g05-build.log), [suite](evidence/p5/g05-suite.log), [detailed](evidence/p5/g05-detailed-tests.log) | Localhost chỉ correctness |
| G05-first byte/integration/race | PASS | `TestFirstByteHookBeforeFullChunk`, TCP/QUIC integration, `make test-race` | Callback khi đọc byte DATA đầu, trước đủ chunk; mốc TCP/QUIC client thực hợp lệ; race suite exit 0 | [detailed](evidence/p5/g05-detailed-tests.log), [race](evidence/p5/g05-race.log) | Không có performance cohort |
| G06-typed files/real trials | PASS | `make build`; `make test`; `make test-race`; `bash docs/evidence/p6/run-g06.sh` | 2 trial cold thành công (TCP, QUIC) và 1 TLS trust failure thật; mỗi trial có raw typed JSON, runs.csv 1 row, streams.csv 6 rows; failure exit 1 nhưng vẫn lưu 6 rows/bytes=0/null timings; cả ba validator PASS | [gate log](evidence/p6/g06-actual-trials.log), [actual records](evidence/p6/actual/), [build](evidence/p6/g06-build.log), [suite](evidence/p6/g06-suite.log), [race](evidence/p6/g06-race.log) | Trial localhost 6×1MiB là dữ liệu correctness, không là benchmark |
| G06-contract/negative checks | PASS | `go test ./internal/metrics`, `python3 analysis/test_validate.py <actual-parent>` | CSV error có comma/quote/newline roundtrip; null ô rỗng; flush error được trả; existing directory không ghi đè; validator đối chiếu schema/raw/CSV/FK/N/công thức, từ chối duplicate run ID và thiếu stream; bản sao gắn warmup có measured_count=2 và warmup_excluded=1 | [detailed](evidence/p5/g05-detailed-tests.log), [validator](evidence/p6/g06-actual-trials.log), [actual records](evidence/p6/actual/) | P9 mới có runner, cohort summary và manifest đầy đủ |
| G07-code/static | PASS | build/test/shell checks P7, recovery script | Bằng chứng lịch sử giữ nguyên; system rerun sau sửa đã có | [P7 evidence](evidence/p7/README.md) | First-load IFB sau fresh boot chưa kiểm |
| G07-first-run (lịch sử) | FAIL, đã recovery/rerun | User system gate UTC 00:23:06Z | IFB host tạo ngoài dự kiến, host comparison FAIL trước transfer; không thay log cũ | [first run](evidence/p7/g07-system.log) | Không là trạng thái G07 hiện hành |
| G07-recovery | PASS | User guarded recovery, recovery_exit=0 | IFB lỗi đã hết, host link/address/route khớp baseline | [recovery log](evidence/p7/g07-host-recovery.log) | Không |
| G07-collision/rollback/topology/UID/ping | PASS | User G07 rerun UTC 01:09:39Z | Collision và rollback đạt; hai vòng setup/idempotence, qclient/qserver/UID1000/ping hai chiều đạt | [rerun](evidence/p7/g07-system-rerun.log) | Không |
| G07-host-state/TCP/QUIC/two-cycles/SIGINT | PASS | Cùng rerun, g07_exit=0; agent kiểm artifacts khi mở P8 | Bốn cold bulk trials mỗi trial 6 hashes/6291456 bytes, server SIGINT exit0 không forced-kill, hai vòng teardown; 18 host snapshot comparisons khớp | [review JSON](evidence/p7/g07-rerun-review.json), [results](../results/p7-g07-vNiIgt/) | Namespace correctness, không là impairment/performance evidence |
| G07-system overall | PASS | User rerun đầy đủ và xác nhận PASS | gate final PASS, g07_exit=0; agent đối chiếu logs/artifacts, không tự nhận chạy sudo | [rerun](evidence/p7/g07-system-rerun.log) | Không |
| G08-code/build/regression | PASS | make build; make test; make test-race; G06 actual CLI regression | exit0, build/suite/race; TCP/QUIC success và TLS failure thật, validator/mutations PASS, mặc định loopback labels giữ nguyên | [build](evidence/p8/g08-build.log), [suite](evidence/p8/g08-go-suite.log), [race](evidence/p8/g08-race.log), [CLI regression](evidence/p8/g08-g06-regression.log) | Localhost chỉ regression, không thay G08 |
| G08-config/units/direction/rollback/offload (unit) | PASS | make test-network | Strict config/duplicate/type/bounds, tc units/loss direction/seed, foreign qdisc/filter refusal, mocked partial tc failure rollback, fixed-ON offload refusal | [Python tests](evidence/p8/g08-python-tests.log) | Không phải actual tc traffic/error/cleanup gate |
| G08-metadata/error-policy (software) | PASS | Go config/CLI/metrics tests; nonroot runner/wrappers | Reject stale/unverified/wrong namespace; failed record giữ network fields; root wrappers và runner không root exit3; shell syntax/dry-run đạt | [suite](evidence/p8/g08-go-suite.log), [static](evidence/p8/g08-static.log), [nonroot](evidence/p8/g08-nonroot.log), [dry-run](evidence/p8/g08-make-dry-run.log) | Live inspect/client metadata cần chạy trong actual G08 |
| G08-IFB/RTT/rate/loss/counters/offloads/seed (actual) | PASS | User: sudo bash tests/system/run.sh --gate G08; g08_exit=0 | 8 trials/48 hashes, baseline RTT0.320/0.325ms và rtt5050.500/50.450ms; seed20260928, offloads/placement/filter/counter/rate verified | [rerun](evidence/p8/g08-system-rerun.log), [review](evidence/p8/g08-rerun-review.json), [results](../results/p8-g08-96nOtS/) | One evidence trial per transport/scenario; no general performance claim |
| G08-switch/tc-error/clear/teardown/SIGINT/host-state (actual) | PASS | Same full gate; child130 expected | ingress→egress→ingress, repeated clear, injected tc-error rollback, parent/child cleanup0, 15 equal host comparisons | [review](evidence/p8/g08-rerun-review.json), [child](../results/p8-g08-qOYl2H/) | SIGKILL not trapped; fresh-boot IFB load unverified |
| G08 overall | PASS | Full user-run gate exit0, agent read-only artifact review | 8 attempted/8 success/0 failed/0 missing; original0/cleanup0 | [P8 evidence](evidence/p8/README.md) | P9 authorized; không dùng G08 làm main cohort |
| G09-code/build/suite/race | PASS | make build; make test; make test-race | exit0, UID1000 ngoài sandbox; final full Go/race suite, fresh QUIC connections and actual TCP/QUIC deadline/cancel failures | [build](evidence/p9/g09-build.log), [suite](evidence/p9/g09-suite.log), [race](evidence/p9/g09-race.log) | Không thay actual main gate |
| G09-plan/config/order/seed/merge | PASS (software) | Go bench tests; actual CLI --plan/entry/merge | default256 planned/240+16; deterministic balanced AB–BA, changed seeds, config/entry refusal, missing/incomplete/foreign cohort/no overwrite | [suite](evidence/p9/g09-suite.log), [actual plan](evidence/p9/actual/default-plan/schedule.json) | Actual main execution PASS ở row riêng |
| G09-CSV/failures/stats/plots | PASS (software/local) | python3 tests/system/run_g09_software.py; make test-analysis; network regression | exit0; success6, TLSfail2, partial4 (1 success/3fail: killed+2not-started), total12 rows/72 resources; CSV-derived summary/PNG/SVG with failures, warmups excluded; median/p95/sample stddev/outliers/checker regressions PASS | [software](evidence/p9/g09-software.log), [review](evidence/p9/g09-software-review.json), [archive/hash](evidence/p9/archive-provenance.json), [stats](evidence/p9/g09-stats.log) | Localhost correctness; không performance claim |
| G09-main240+16/1536/manifest/actual network | PASS | User full rerun g09_exit=0; agent read-only review | 256 invoked/256 success/0fail/0missing;240 measured+16warmup/1536 hash rows;1286 kernel snapshots/256 counter+idle checks/four RTT probes;stats recomputed | [review](evidence/p9/g09-rerun-review.json), [log](evidence/p9/g09-system-run2.log), [archive](evidence/p9/g09-user-run-artifacts.tar.gz) | No numeric superiority/HOL proof |
| G09-actual controlled interrupted/UID/cleanup/host | PASS | Separate child actual SIGINT130; outside-sandbox read-only resource check | 2 planned/1invoked/2failed/12 resource rows; child/main cleanup0, equal host snapshots, no managed processes/namespaces | [review](evidence/p9/g09-rerun-review.json) | Interactive terminal Ctrl+C through tee previously141/cleanup1 remains unfixed |
| G09 overall | PASS | Full user-run actual gate + agent artifact review | User g09_exit=0, main_exit=0/interrupt_exit130; dataset and controlled cleanup validated | [P9 evidence](evidence/p9/README.md) | Historical P9 scope; interactive Ctrl+C limitation retained |
| G10-build/suite/race | PASS | make build/test/test-race | Final source build/test/race exit0, UID1000 ngoài sandbox; failed first rejection/fixture and sandbox logs giữ history | [P10 evidence](evidence/p10/README.md) | Không thay network gate |
| G10-ticket/cold/resumed/accepted | PASS (actual localhost) | RunSession integration + canonical checker | Cache notification/deadline; actual DidResume/Used0RTT đúng; own prior/target t0; bytes/FIN/hash đúng | [functional archive/review](evidence/p10/README.md) | Packet0RTT corroboration thuộc G11 |
| G10-rejected/one-replay/no-duplicate | PASS (actual localhost) | Valid-ticket fixed-key acceptance hook, six workers | DidResume=true/Used=false/rejected=true, fallback1, attempts0/1 same t0;2 connections/12 REQUESTs (6 prior+6 replay), final6144 bytes/six hashes | [functional evidence](evidence/p10/README.md) | Actual impaired rejection trace chưa thuộc P10 dataset |
| G10-missing-ticket/handshake-failure/cancel | PASS (actual localhost) | Negative integration + canonical rows/history | Bounded errors, no extra replay; missing ticket không invoke target; state unknown giữ null; failures không bị lọc | [functional evidence](evidence/p10/README.md) | Không |
| G10-handshake96/64tickets/cohort/stats/plots | PASS (software/local) | run_g10_software.py + checker/analysis tests |96/96 transfer success,90 measured+6 target warmups/96 streams,64 separate ticket warmups; measured API-qualified cold30/resumed30/early29, early1 unachieved excluded latency; wronghostname3/3 fail | [software review/archive](evidence/p10/README.md) | Loopback only, không performance claim |
| G10-actual90+6/IFB/RTT/kernel/UID/cleanup | PASS | User full gate + checker trên copy |96 success/0fail,96 streams,64 separate tickets; cold/resumed/early30 measured API-qualified mỗi mode; four RTT probes, claims/journals/kernel/counters/idle và cleanup0/host unchanged | [1836 hashes/archive review](evidence/p10/g10-rerun-review.json) | Packet proof thuộc G11 |
| G10 overall | PASS | Actual user-run results/p10-g10-cR1oR9 + audit | Functional7 và actual96+64/cleanup PASS | [P10](evidence/p10/README.md) | Giữ historical BLOCKED logs |
| G11-qlog/progress/viewer | PASS (localhost) | run_g11_software.py + check_g11.py --software | Actual client/server quic-12 JSON-SEQ parsed, ODCID/endpoint correlation, bounded progress and PNG opened | [P11](evidence/p11/README.md) | Actual packet/IFB proof ở row riêng bên dưới |
| G11-build/suite/race/regressions | PASS | build/suite/race/evidence mutation tests | Exclusive0600 sinks/flush/errors, six-worker rejection attempt accounting, failure denominator, conservative proof checks | [P11 logs](evidence/p11/README.md) | Actual lifecycle full G11 verified ở row riêng bên dưới |
| G11-PCAP/UDP | PASS actual | Full user-run paired decode + original checker/read-only audit |46 complete capture directories/282370 packet records,drop0/cleanup0; UDP/QUIC decoded by tshark4.6.4 | [audit](evidence/p11/g11-rerun-review.json), [original check](../results/p11-g11-6a8cc99602b7/g11-check.json) | Keylogs/PCAP remain local; browser rendering unverified |
| G11-early-secret export | PASS actual localhost | D28 hash-checked build-only TLS overlay | Accepted client/server match; cold/resumed none; rejected client only; writer errors propagated | [six cases](evidence/p11/g11-early-detail.log), [review](evidence/p11/g11-early-secret-review.json) | Packet proof verified ở row riêng bên dưới |
| G11-early REQUEST | PASS actual | Paired decrypted PCAP + API/native stream/qlog |handshake_early actual DidResume/Used0RTT=true,fallback0; both captures frame14/PN0/stream0/resource1/exact32-byte QB01 REQUEST; reqEnd1.945624ms < observed handshake56.605283ms | [audit](evidence/p11/g11-rerun-review.json), [precheck](../results/p11-g11-6a8cc99602b7/early-packet-check.json) | Timing alone not proof; request client→server |
| G11-actual23/IFB/capture | PASS actual | User full G11 entry, original_exit0/cleanup0 |23 planned/invoked/success,0failed;123 hashes,7683 payload points,30 qlogs; four RTT probes/verified IFB/idle/UID/host unchanged | [log](evidence/p11/g11-user-run.AGayVd.log), [audit](evidence/p11/g11-rerun-review.json) | Instrumented cohort excluded performance |
| G11-D27-user-run (lịch sử) | FAIL, superseded by full rerun | User-run3344e60b5868 |5/23 successes, shutdown failure/three short empty captures;cleanup0/host unchanged | [D27 audit](evidence/p11/g11-fix-user-review.json), [log](evidence/p11/g11-user-run.DC0kWH.log) | Original artifacts/receipts preserved |
| G11-D29-user-run (lịch sử) | FAIL, superseded by full rerun | User-run1200e3df1cf2 |0/23 before topology; owner PATH lacked sbin/sysctl;cleanup0/host unchanged | [D29 audit](evidence/p11/g11-path-review.json), [log](evidence/p11/g11-user-run.Jbm1be.log) | Original14 artifacts preserved |
| G11-fix regressions | PASS software | Full Go/race, early6, provenance4, lifecycle8, detectors6 | Actual early labels match; accepted/rejected/writer errors/source drift checked | [fix logs](evidence/p11/README.md) | Actual full network PASS ở row riêng bên dưới |
| G11-owner PATH/runtime | PASS software/real metadata | Production owner helper/setpriv/reset-env/real sysctl,9 tests |7 sysctl values +8 tools resolve, UID1000 | [D29](evidence/p11/g11-path-review.json), [tests](evidence/p11/g11-path-lifecycle.log) | Not full network proof |
| G11-HOL causal trace | PASS actual | Conservative checker, first qualifying retained pair |loss_0_tcp ACK/SACK gap+later bytes+retransmission+app stall;loss_0_quic lostPN25/stream20/resource6,gap1345/later2602,sibling resource5 progress before recoveryPN50 | [audit/witnesses](evidence/p11/g11-rerun-review.json), [annotated notes](../results/p11-g11-6a8cc99602b7/evidence-notes.md) | Same-host wall3ms/validated16KiB sampling; shared congestion/flow/packet streams |
| G11 overall | PASS | Full user-run g11_exit0, original checker and independent read-only audit |qlog/progress/UDP/early/HOL PASS,full_demo_complete=true; immutable source receipt/archive662 files byte-verified | [status](evidence/p11/g11-status.json), [audit](evidence/p11/g11-rerun-review.json), [checker replay log](evidence/p11/g11-rerun-check.log) | Original inventory797/798 match; self-open logs/check.log exception independently recorded, no rewrite |
| G12-fresh-checkout/build/tests/analysis/package | PASS |User bash scripts/run-g12-review.sh;14softwaresteps exit0,UID1000 |Fresh local checkout+candidate610sourcehashes,empty app/cert/results/buildcache;Go/Python/demo12/G1224,localhost5success+1expectedTLSfailure,1028canonicalhashes unchanged |[closure audit](evidence/p12/g12-rerun-review.json),[receipt](../results/p12-g12-51c13b94f99b/software.json)|Prepared offline caches reused; candidate not new committed revision |
| G12-Make demos/IFB/cleanup user7807 (historical) | PASS | bash scripts/run-g12-review.sh; read-only independent replay |Four Make exits0;8/8 successful trials, decoded UDP/early REQUEST/live HOL, cleanup0/host unchanged; instrumentation cohort only | [as-run audit](evidence/p12/g12-user-fail-review.json) | As-run timing FAIL retained; latest51c13 rerun PASS below |
| G12-docs/disclosure/traceability | PASS |Final README/report/runbook/outline/source hashes/link audit |Real P9/P10/P11 denominators/statistics/causal witnesses, AI contribution and human review pending; original3 sources unchanged | [report](REPORT.md), [P12](evidence/p12/README.md), [AI](AI_USAGE.md), [traceability](TRACEABILITY.md) | Human spoken delivery/code ownership/deck submission not certified |
| G12-rehearsal5–7min user7807 (historical) | FAIL | Actual unprivileged timed Make walkthrough |423.01996559s>420s; baseline97.220724s wrongly included in A→C→B live timeline; final checker NOT_RUN | [as-run audit](evidence/p12/g12-user-fail-review.json), [driver](../scripts/g12-rehearse.py) | Superseded by actual51c13 PASS; original timing retained |
| G12-Make demos/IFB/cleanup user51c13 | PASS |All-four-demo actual artifacts+read-only verifier |8planned/invoked/success,0failed/missing;paired PCAP/qlog/progress,UDP/early/HOLPASS;allcleanup0/hostunchanged |[closure audit](evidence/p12/g12-rerun-review.json)|Instrumented one-sample demos excluded from main performance cohorts |
| G12-rehearsal5–7min user51c13 | PASS |Actual schema2 clock+hash-bound preparation+exact Make argv/logs |Live360.000793725s within300–420;preparation177.218538684s before A→C→B;all Make exits0 |[rehearsal](../results/p12-g12-51c13b94f99b/rehearsal.json),[audit](evidence/p12/g12-rerun-review.json)|Timed terminal walkthrough; spoken delivery not certified |
| G12 overall | PASS |User full entry g12_exit0;as-run fullchecker+independent read-only audit |Actual51c13b94f99b:software14/14,610sourcefiles,all-four-demo8/8success;UDP/early/liveHOL/cleanupPASS;live360.000794s,baseline177.218539s separate |[user log](evidence/p12/g12-user-run.RUbjTU.log),[closure audit](evidence/p12/g12-rerun-review.json),[full checker](../results/p12-g12-51c13b94f99b/g12-check.json)|Human code/oral/browser/video/deck review pending; no auto commit/upload |


## Lệnh tái lập P0

Lệnh cài Go exact version + checksum ở README; không cần sudo cho download/build/test. Từ repo root:

```bash
make build
make test
make doctor REPORT=results/p0-review/doctor.txt
# Chỉ khi chưa có cert; không force identity đang dùng:
make certs
openssl verify -CAfile certs/server.crt -verify_hostname localhost certs/server.crt
openssl verify -CAfile certs/server.crt -verify_ip 127.0.0.1 certs/server.crt
openssl verify -CAfile certs/server.crt -verify_ip 10.10.0.2 certs/server.crt
mkdir -p results/p0-review
set -o pipefail
sudo bash scripts/preflight-network.sh 2>&1 | tee results/p0-review/network-probe.log
```

Người dùng nhập mật khẩu sudo trong terminal của mình. Agent không nhận/ghi mật khẩu. Probe tạo/xóa namespace tạm riêng, veth/IFB, ingress redirect và netem 50ms; không tạo qclient/qserver hoặc chạy app. Log lần chạy nêu trên đã được review và đóng capability G00; không pass G07/G08. Các lỗi sudo/netlink trước đây vẫn giữ trong evidence làm lịch sử, không còn là blocker hiện tại của G00. Người dùng đã cho phép P1/P2 trong phiên hiện tại.

## Tái lập P1/P2

```bash
make test
make test-race
make build
bin/server --transport=tcp --profile=handshake --listen=127.0.0.1:14433
# Terminal khác, cùng repo:
bin/client --transport=tcp --profile=handshake --addr=127.0.0.1:14433 --server-name=localhost --format=json
```

Lệnh CLI chạy UID thường, dùng certificate local từ P0. Nếu chưa có cert, chạy `make certs` trước khi mở server. Dừng server bằng Ctrl+C. G02 chạy localhost thực ngoài sandbox vì sandbox chặn tạo socket; không có network impairment hay số liệu performance. JSON ở P2 là kết quả tối thiểu trên stdout, chưa phải canonical artifacts P6.

## Tái lập P3/G03

```bash
make build
make test
make test-race
GOPATH="$PWD/.tools/gopath" GOCACHE="$PWD/.tools/gocache" GOTOOLCHAIN=local GOMAXPROCS=2 GOFLAGS=-p=2 .tools/go1.27.1/bin/go test -mod=readonly -count=1 -v ./internal/protocol ./internal/transport/tcp ./tests/integration
bin/server --transport=tcp --profile=bulk --listen=127.0.0.1:14435
# Terminal khác, cùng repo:
bin/client --transport=tcp --profile=bulk --addr=127.0.0.1:14435 --server-name=localhost --format=json
```

Chạy dưới UID thường trong Ubuntu WSL2 và dừng server bằng Ctrl+C. Nếu chưa có cert thì `make certs` trước. G03 chỉ xác nhận multiplex/correctness ở localhost; chưa áp qclient/qserver, netem, IFB hoặc tạo benchmark CSV.

## Tái lập P4/G04

```bash
make build
make test
make test-race
GOPATH="$PWD/.tools/gopath" GOCACHE="$PWD/.tools/gocache" GOTOOLCHAIN=local GOMAXPROCS=2 GOFLAGS=-p=2 .tools/go1.27.1/bin/go test -mod=readonly -count=1 -v -run '^TestQUIC' ./tests/integration
# Terminal 1, nếu chưa có cert thì chạy make certs trước:
bin/server --transport=both --profile=bulk --listen=127.0.0.1:4433 --ready-file=results/p4-ready.txt
# Terminal 2, cùng repo:
bin/client --transport=tcp --mode=cold --profile=bulk --addr=127.0.0.1:4433 --server-name=localhost --format=json
bin/client --transport=quic --mode=cold --profile=bulk --addr=127.0.0.1:4433 --server-name=localhost --format=json
```

Tạo thư mục `results/` trước nếu dùng ready-file như ví dụ; dừng server bằng Ctrl+C. G04 chạy localhost thật dưới UID thường ngoài sandbox hạn chế socket; lần thử sandbox cũ bị EPERM, không coi là lỗi ứng dụng. Log và JSON tại `docs/evidence/p4/` là correctness evidence, không phải benchmark dataset hoặc kết quả G07/G08. Client resumed/early, qlog, canonical CSV và network impairment thuộc các gate sau.

## Tái lập P5/G05 và P6/G06

```bash
make build
make test
make test-race
GOPATH="$PWD/.tools/gopath" GOCACHE="$PWD/.tools/gocache" GOTOOLCHAIN=local GOMAXPROCS=2 GOFLAGS=-p=2 .tools/go1.27.1/bin/go test -mod=readonly -count=1 -v ./internal/metrics ./internal/protocol ./tests/integration
bash docs/evidence/p6/run-g06.sh
# Script in ra results_dir mới; thay PATH bằng path vừa in:
python3 analysis/validate.py PATH/tcp_success
python3 analysis/validate.py PATH/quic_success
python3 analysis/validate.py PATH/tcp_failure
python3 analysis/test_validate.py PATH
```

Chạy dưới UID thường trong Ubuntu WSL2 có quyền socket localhost. Script chọn port tạm, tạo thư mục `results/p6-g06-*` mới, dừng server do chính script tạo và không ghi đè kết quả cũ. Lần đầu script dùng port 0 bị CLI từ chối ở preflight; script đã sửa để chọn port hợp lệ, lần chạy gate cuối exit 0. Bản dữ liệu thật đã sao lưu ở `docs/evidence/p6/actual/`; original path lần cuối là `results/p6-g06-ag6vK3/`. Các timestamp/latency ở đây không dùng để so sánh hiệu năng.

Checkpoint lịch sử P5/P6: P5 đặt công thức và mốc client. P6 thêm canonical raw JSON/CSV và validator. CLI cold transfer hiện ghi `results/<experiment_id>/` theo mặc định hoặc thư mục mới từ `--out`; `--experiment-id/--run-id` tự sinh nếu thiếu. Mỗi invocation là một trial, không append. `--out` đã tồn tại hoặc write/flush lỗi trả exit 1; raw đã ghi được giữ lại nếu CSV lỗi và `INCOMPLETE` marker còn hiện diện. Tại checkpoint P6 chưa có `manifest.json` thí nghiệm đầy đủ, schedule/merge, main cohort, progress events hoặc thống kê/plots; chúng thuộc P9/P11/P12. Tại checkpoint P6 `docs/REPORT.md` là template; current P12 report dùng actual P9/P10/P11.

## P7/G07 — recovery và rerun đã PASS

Log lỗi đầu giữ ở evidence/p7/g07-system.log. Người dùng đã chạy guarded recovery exit0 và G07 rerun exit0 (UTC 01:09:39Z), kết quả `results/p7-g07-vNiIgt/`; agent kiểm bốn CSV trials/6 stream rows và 18 comparisons host snapshots khi mở P8. Chi tiết/hash ở evidence/p7/g07-rerun-review.json. Không cần recovery lại trong trạng thái hiện tại. P7 raw vẫn loopback-test cho correctness; first-load IFB sau fresh boot còn chưa kiểm.

## Tái lập P8/G08 và review

Lệnh/full matrix/files/evidence ở [P8 runbook](evidence/p8/README.md). Actual rerun PASS với results/p8-g08-96nOtS/ và SIGINT child p8-g08-qOYl2H/. Không cần chạy lại để đóng gate; khi cần tái lập, lưu log mới trong terminal Ubuntu WSL2 từ repo root, không có topology/server cũ:

```bash
make build
make test-network
test -r certs/server.crt && test -r certs/server.key || make certs
set -o pipefail
sudo bash tests/system/run.sh --gate G08 2>&1 | tee docs/evidence/p8/g08-system-review.log
g08_status=${PIPESTATUS[0]}; printf 'g08_exit=%s\n' "$g08_status" | tee -a docs/evidence/p8/g08-system-review.log
```

Review receiver IFB/flower direction, tc JSON units/seed, offload fixed/absent handling, reset sau probes, counter before/after/drop/backlog và rate upper sanity. Review exception/signal rollback + host comparison, root ownership/UID split, snapshot client identity/freshness + evidence labels và failure rows. Snapshot không khóa kernel trong transfer; wrappers phải verify trước/sau. Downstream loss không DATA-only, drops không phải empirical random probability. Nếu kernel/tc không hỗ trợ seed, explicit NETEM_SEED=none được document trong runbook, không silently downgrade. Không mở P9 trước actual G08 PASS.

## Review thay đổi P4 (checkpoint lịch sử)

- `internal/transport/quic`: per-connection batch coordinator bắt đầu deadline từ REQUEST hợp lệ đầu, xác nhận EOF sau request, hủy cả connection khi một stream lỗi; mỗi response worker tự ghi META/DATA/FIN/Close trên native stream, không có QUIC response-write lock chung. `StreamID()` lấy trực tiếp từ quic-go; client chỉ hash sau khi tất cả FIN/EOF hoàn tất.
- `internal/cli` và TCP listener: hai socket được bind trước readiness, dùng một store/cert, giới hạn 8 active connections chung; ready-file atomically công bố và không ghi đè marker có sẵn. QUIC v1 cold path, flow credits và 64 incoming server streams ở `internal/transport/quic/config.go`/`docs/VERSIONS.md`.
- Test/G04 mới xác nhận chức năng loopback và race. Chưa xác nhận lợi thế hiệu năng, network loss/HOL hay 0-RTT. Đây là self-review của agent; không ghi rằng người dùng/nhóm đã duyệt P4.

## Review thay đổi P0 (lịch sử tại thời điểm P0)

- go.mod/go.sum và Makefile: pin exact dependency, bắt đúng Go, GOTOOLCHAIN=local; cache/toolchain local gitignored. Build/test unprivileged và không tự chạy benchmark.
- internal/config: config tối đa 1 MiB/độ sâu 32; reject duplicate/unknown/trailing, kiểm count/size/total trước workload allocation; không có resource generator P1.
- internal/cli và ba mains: thống nhất flags/defaults, lỗi input 2, chưa triển khai 1; help/version 0. Không tạo readiness hoặc result success giả.
- internal/tlsconfig, gen-cert: trust rõ ràng, TLS1.3/ALPN, SAN, private key 0600; tests âm cho sai tên/CA và overwrite. Cert/key thật chỉ local, không đưa vào diff.
- doctor/probe: inventory và đặc quyền tách riêng; người dùng đã chạy thành công đường tạo/xóa tài nguyên bình thường. Dòng PASS được in sau lệnh xóa namespace dưới set -e; không suy ra cleanup khi lỗi/interrupt hoặc topology G07 đã được kiểm chứng.
- API pin: compile/source checks không tương đương network test. Runtime handshake/ticket/rejection/qlog/viewer còn để đúng phase sau.

Đây là self-review của agent; người dùng đã chạy/xác nhận probe, chưa có xác nhận review toàn bộ code. Không phát hiện thay đổi ngoài scope P0 trong code. Không chạy test-race vì P0 không có app concurrency; target sẵn cho phase phù hợp. Originals, source manifests, configs và result schema giữ nguyên; không commit. Diff đầy đủ (kể cả file mới) được cung cấp khi bàn giao, không chỉ git diff mặc định vốn bỏ qua untracked files.

## Audit fixes P0–P6 — 2026-09-30

User authorized the six review fixes only. G04/G05/G06 regression checks **PASS**: build, full Go suite, full race suite, G06 actual TCP/QUIC success + TLS failure and Python mutation regressions. Evidence and reproduction: [audit-p0-p6/README.md](evidence/audit-p0-p6/README.md). Actual additional QUIC resolve/socket failures retain raw JSON plus N stream rows. Historical sandbox denial and intermediate EOF-timeout regression failure are retained separately; neither remains a final blocker. At that audit checkpoint G07–G12 were NOT_RUN; the current G07 status is recorded in the table above.

## Tái lập P9/G09 (checkpoint lịch sử trước khi user xác nhận PASS)

Full commands, exit capture, seed-null option, artifact expectations và review: [evidence/p9/README.md](evidence/p9/README.md). Run trong terminal Ubuntu WSL2 từ repo root: build/deps/cert bằng user, topology/server absent, `sudo bash tests/system/run.sh --gate G09`. Khi blocked hiện tại không có main result path để đưa vào report; source software data ở results/p9-software-6011935o/, archive là localhost correctness. Không chạy P10 cho đến khi được cho phép riêng.

Checkpoint hiện hành: G11 actual PASS tại `results/p11-g11-6a8cc99602b7`; D27/D29 FAIL và earlier sudo BLOCKED giữ như lịch sử. P12/G12 authorized, entry `bash scripts/run-g12-review.sh`; trạng thái thực mới nhất ở [P12](evidence/p12/README.md) và [TASK](../.codex/TASK.md).
