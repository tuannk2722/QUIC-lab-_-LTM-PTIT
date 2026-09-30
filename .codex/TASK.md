# Tiến độ công việc

## Phiên 2026-09-30 — P4/G04 được người dùng cho phép, gate PASS, dừng review

- Phạm vi: chỉ QUIC multiple streams P4 và gate G04/G40 theo yêu cầu mới; dừng để human review sau gate. Trạng thái đầu phiên: commit `65d5a7b` (P3), worktree sạch; P0–P3 đã ghi PASS, chưa suy ra G04.
- Read set trước thay đổi: `AGENTS.md`, `docs/00-INDEX.md`, `.codex/TASK.md`; `docs/IMPLEMENTATION_PLAN.md` §P4/G04, `docs/PROTOCOL.md`, `docs/DEMO_SPEC.md`, `docs/CLI_CONTRACT.md`, `docs/METRICS_AND_RESULTS.md`, `docs/NETWORK_AND_BENCHMARK.md` §1, `docs/ACCEPTANCE.md`, `docs/ACCEPTANCE_RESULTS.md`, `docs/CONTEXT_AND_DECISIONS.md`, `docs/VERSIONS.md`, `docs/AI_USAGE.md`; `configs/workloads.json`, `go.mod`, pinned quic-go v0.63.0 source `interface.go`/`stream.go`/server/client API; `internal/{cli,config,protocol,tlsconfig,transport/tcp,transport/types,workload}` và `tests/{api,integration}` cùng Makefile. Đã inspect current code/tests và listener/CLI behavior.
- Bước kế tiếp: implement QUIC cold client/server trên cùng QB01/store/cert, per-connection batch coordinator và per-stream workers với close/cancel/EOF/deadline; expose actual stream ID mapping trong kết quả tối thiểu; server `both` bind TCP+UDP cùng cổng và ready sau cả hai. Viết integration cho 1 connection/6 streams, concurrent request/barrier, invalid frame/EOF/cancel/extra stream, chạy build/suite/race/CLI localhost thực và lưu evidence G04.
- Read set trước cập nhật hướng dẫn P4: `README.md`, `START_HERE.md`, `docs/{00-INDEX,CLI_CONTRACT,VERSIONS,AI_USAGE}.md` và code hiện tại `internal/transport/quic/{config,server,client,streams}.go`, `internal/cli/cli.go`, `internal/transport/{types,tcp/server}.go`, `configs/workloads.json`; hợp đồng P4 đã đọc ở mục trên. Bước kế tiếp cho docs: mô tả cold TCP+QUIC, actual stream ID, readiness/credit/limit và giới hạn phase sau; chưa ghi G04 PASS trước khi evidence hoàn tất.
- P4/G04 **PASS**, dừng human review. Client cold QUIC mở N bidirectional streams theo ResourceID, lưu `StreamID()` thật, gửi REQUEST trên các workers độc lập và Close send-half; response mỗi stream phải có META/DATA/FIN/EOF, mọi hash chỉ chạy sau khi toàn bộ streams hoàn tất. Server accept loop nhận tối đa N streams/connection, coordinator validate batch và EOF từng request, 5s deadline từ REQUEST hợp lệ đầu, trial deadline toàn connection; worker lỗi hủy cả trial/đánh thức workers. Mỗi worker response tự ghi trên stream, không có global QUIC writer lock. Pinned quic-go v0.63.0/QUIC v1; server nhận 64 bidirectional streams, client từ chối unsolicited streams, hai phía từ chối incoming unidirectional; receive credits stream 512KiB→2MiB, connection 2MiB→16MiB. Handshake idle bound được đặt một nửa 10s total bound theo API pin; client có dial deadline. Chi tiết refinement ở D16.
- Server CLI `both` bind TCP+UDP cùng số port trước readiness, dùng một store/certificate/limiter 8 active connections; ready file được công bố atomically và từ chối marker có sẵn. TCP Serve tách listener đã bind để chia sẻ lifecycle. CLI JSON tối thiểu thêm `transport_stream_id` cho QUIC; canonical metrics/results vẫn thuộc P5/P6. `G40` trong request không có acceptance ID; thực hiện đúng G04 của P4.
- Files changed P4: mới `internal/transport/quic/{config,client,server,streams}.go`, `tests/integration/quic_test.go`, `docs/evidence/p4/{g04-build.log,g04-suite.log,g04-detailed-tests.log,g04-race.log,g04-cli-transfer.log,tcp-transfer.json,quic-transfer.json}`; sửa `internal/transport/{types.go,tcp/server.go}`, `internal/cli/{cli.go,cli_test.go}`, `.codex/TASK.md`, `docs/{ACCEPTANCE_RESULTS,AI_USAGE,CLI_CONTRACT,CONTEXT_AND_DECISIONS,VERSIONS,00-INDEX}.md`, `README.md`, `START_HERE.md`. Không sửa config/schema/originals, không commit, không tạo CSV/benchmark dataset.
- Gate evidence thực: `make build` exit 0; `make test` exit 0; `go test -mod=readonly -count=1 -v -run '^TestQUIC' ./tests/integration` với env Makefile exit 0; `make test-race` exit 0. Detailed integration: một QUIC connection/6 distinct native stream IDs và 6×1MiB SHA-256 pass; TCP cùng port/store pass; barrier và concurrent requests, missing/duplicate/invalid/truncated/non-EOF/extra stream, server cancel, client EOF trước FIN và untrusted CA đều kiểm bounded; race suite sạch. CLI server `both` trên `127.0.0.1:4433` ready TCP+UDP; TCP và QUIC client exit 0, mỗi transport 6 resources/6.291.456 bytes/6 checksum true; QUIC stream map 1→0, 2→4, 3→8, 4→12, 5→16, 6→20 quan sát trong lần chạy thực (không hardcode), server SIGTERM exit 0, ready file xóa. Paths/lệnh tái lập ở `docs/ACCEPTANCE_RESULTS.md`.
- Test socket trong sandbox hạn chế từng trả EPERM ở lượt thử của test agent; các log gate cuối chạy unprivileged UID 1000 ngoài sandbox với quyền localhost hợp lệ và đều PASS. Localhost chỉ xác nhận correctness, không là số liệu hiệu năng hay G07/G08. `elapsed_ms` trong JSON chỉ output tối thiểu; G05–G12 NOT_RUN, 0-RTT/CSV/qlog/network testbed chưa triển khai. Người dùng chưa xác nhận review P1/P2/P3/P4.
- Bước tiếp theo chính xác: người dùng review diff P4, evidence G04, đặc biệt coordinator fail/cancel/deadline, per-stream EOF/Close, native stream map, dual listener/readiness và flow limits. Chỉ mở P5/G05 khi được cho phép rõ ràng. Final hygiene: `git diff --check` PASS, `gofmt -l` rỗng trên Go files thay đổi; chưa commit.

## Phiên 2026-09-30 — P3/G03 được người dùng cho phép

- Phạm vi: chỉ TCP multiplex P3 và gate G03; dừng để human review sau gate. Trạng thái trước sửa: P1/G01 và P2/G02 PASS, worktree sạch.
- Read set trước thay đổi: AGENTS.md, docs/00-INDEX.md, .codex/TASK.md; docs/IMPLEMENTATION_PLAN.md §P3/G03, docs/PROTOCOL.md, docs/DEMO_SPEC.md, docs/CLI_CONTRACT.md, docs/METRICS_AND_RESULTS.md, docs/ACCEPTANCE.md, docs/ACCEPTANCE_RESULTS.md, docs/CONTEXT_AND_DECISIONS.md, docs/AI_USAGE.md; configs/workloads.json; internal/protocol/{frame,codec,request,response,errors,protocol_test}.go, internal/transport/{types,tcp/client,tcp/server}.go, internal/workload/resource.go, internal/cli/cli.go, tests/integration/tcp_test.go và Makefile.
- Bước kế tiếp: thêm batch validator, TCP scheduler một writer, client batch demux, CLI bulk; kiểm transcript thứ tự frame, một TLS connection/6 hash, batch timeout/cancel/race. Sau đó cập nhật evidence/G03/task và dừng.
- P3/G03 **PASS**, dừng human review. `internal/protocol/batch.go` kiểm REQUEST count/chunk/IDs/duplicate; server thu đủ batch với deadline 5s từ request hợp lệ đầu (theo config), rồi `internal/transport/tcp/scheduler.go` ghi META tất cả và DATA mỗi ID một chunk/vòng, FIN ngay sau chunk cuối. Một TLS connection/response writer, một client decoder demux; hash chỉ verify sau khi mọi FIN đã tới. Client gửi REQUEST IDs tăng dần và CloseWrite sau batch; server giám sát request thừa/EOF trong khi viết. Đây là lựa chọn thực thi phù hợp PROTOCOL§3/§5, không mở rộng wire format.
- Files changed P3: `internal/protocol/{batch.go,batch_test.go,codec.go}`, `internal/transport/tcp/{client.go,server.go,scheduler.go,scheduler_test.go}`, `internal/cli/{cli.go,cli_test.go}`, `tests/integration/tcp_test.go`; docs `.codex/TASK.md`, `docs/{ACCEPTANCE_RESULTS.md,AI_USAGE.md,00-INDEX.md,CLI_CONTRACT.md}`, `README.md`, `START_HERE.md`; evidence `docs/evidence/p3/{g03-build.log,g03-suite.log,g03-detailed-tests.log,g03-race.log,g03-cli-transfer.log}`. Không sửa config/schema/originals, không commit, không tạo benchmark dataset.
- Gate evidence thực, Ubuntu WSL2 native Linux, UID thường: `make build` exit 0; `make test` exit 0; `go test -mod=readonly -count=1 -v ./internal/protocol ./internal/transport/tcp ./tests/integration` với env Makefile exit 0; `make test-race` exit 0. Transcript 6 resources/30 frames với 3 DATA rounds; integration accepted TCP/TLS connections=1, 6×1MiB và 6 SHA-256 pass; batch thiếu trả ERROR 6 sau 100ms test, duplicate trả ERROR 3, cancellation release handler; full race suite sạch. CLI bulk exit 0, server SIGTERM exit 0, JSON 6 resource/6.291.456 bytes/6 checksum true. Paths và reproduction ở `docs/ACCEPTANCE_RESULTS.md`.
- Lượt `make test` đầu trong sandbox bị chặn `listen tcp ... socket: operation not permitted`; đã chạy lại ngoài sandbox với localhost permission hợp lệ và PASS. Test CLI cũ giả định bulk chưa triển khai đã được cập nhật để kiểm QUIC chưa triển khai và input error đúng. Các lỗi này không còn là gate blocker. Localhost chỉ kiểm correctness; không có G07/G08 hoặc performance claim. G04–G12 NOT_RUN, P1/P2 chưa có xác nhận human review.
- Bước tiếp theo chính xác: người dùng review P3 diff/evidence G03; chỉ bắt đầu P4/G04 khi người dùng cho phép rõ ràng. Điểm review: batch timeout/extra-request monitor, single writer round-robin, client CloseWrite/demux/FIN/hash và output CLI tạm trước P5/P6.
- Final hygiene: `git diff --check` PASS, `gofmt -l` rỗng cho toàn bộ Go files thay đổi; worktree có code/docs/evidence P3 chưa commit. Không chạy thêm gate sau kiểm chứng đầy đủ.

## Phiên 2026-09-30 — P1 rồi P2 theo yêu cầu mới

- Người dùng xác nhận P0/G00 đã human-review/approved; cho phép P1 và P2 tuần tự, giữ G01/G02. Trạng thái hiện tại: **P1/G01 PASS; P2/G02 PASS; dừng chờ human review, P3 NOT_STARTED**.
- Read set trước thay đổi P1: AGENTS.md, docs/00-INDEX.md, .codex/TASK.md, docs/IMPLEMENTATION_PLAN.md, docs/DEMO_SPEC.md, docs/PROTOCOL.md, docs/CLI_CONTRACT.md, docs/METRICS_AND_RESULTS.md, docs/NETWORK_AND_BENCHMARK.md, docs/ACCEPTANCE.md, docs/CONTEXT_AND_DECISIONS.md, docs/ACCEPTANCE_RESULTS.md, docs/AI_USAGE.md, configs/workloads.json; code internal/config/{config,json}.go và config_test.go, internal/cli/cli.go, internal/tlsconfig/config.go, Makefile; inventory internal/cmd/tests và git status (sạch).
- P1 PASS / G01 PASS. Đã thêm internal/workload/{resource,generator,workload_test}.go và docs/evidence/p1/{g01-workload-tests.log,g01-suite.log,g01-race.log,workload-manifest.json}. Store giữ backing bytes private, Resource trả bằng value, ReadAt copy; cả TCP/QUIC sẽ nhận cùng Store pointer khi các listener được xây. G01 kiểm hai reader đồng thời cùng Store; cross-transport runtime còn thuộc G04.
- G01: `go test -v ./internal/workload` exit 0 sau khi đặt env cache theo Makefile; `make test` exit 0; `go test -race ./internal/workload` exit 0. Lần gọi gofmt/go test đầu thất bại do PATH/cache mặc định read-only, đã sửa bằng toolchain/cache local và rerun. Manifest sinh từ log test thực, không phải benchmark.
- Bước tiếp theo: inspect mã/tests CLI/TLS và hợp đồng P2 trước sửa; implement đúng một resource QB01 + TCP/TLS và chạy G02. Không mở batch/multiplex P3.
- Read set P2 trước sửa: docs/PROTOCOL.md (toàn bộ), docs/DEMO_SPEC.md, docs/CLI_CONTRACT.md, docs/IMPLEMENTATION_PLAN.md §P2/G02, docs/ACCEPTANCE.md và docs/METRICS_AND_RESULTS.md; cmd/{server,client}/main.go, internal/cli/{cli,cli_test}.go, internal/tlsconfig/{config,config_test}.go, internal/workload code/tests, Makefile. P2 IN_PROGRESS. Bước kế tiếp: codec/state QB01 bounded, TCP/TLS single-resource client/server/CLI, parser/fuzz/integration tests, chạy G02 localhost thực.
- P2/G02 PASS: thêm internal/protocol/{frame,codec,request,response,errors,protocol_test}.go, internal/transport/types.go, internal/transport/tcp/{client,server}.go, tests/integration/tcp_test.go; sửa internal/cli/cli.go để chỉ TCP/TLS một resource hoạt động, mode/transport tương lai vẫn nonzero. Không có P3 scheduler/batch multiplex. Codecs giới hạn payload trước allocate, xử lý short read/write/EOF/cancel/timeouts; client đối chiếu META, bytes, FIN, SHA-256; TLS trust/ALPN/TLS1.3 từ P0.
- G02 commands/results: `make build` exit 0; `make test` exit 0 ngoài sandbox cho localhost (sau lần chạy trong sandbox bị chặn bind); `go test -v -count=1 ./internal/protocol ./tests/integration` exit 0 gồm fuzz seeds; `make test-race` exit 0; CLI localhost thật client 1024 bytes/checksum true exit 0, CA khác exit 1, server SIGTERM exit 0. Evidence: docs/evidence/p2/{g02-build.log,g02-suite.log,g02-detailed-tests.log,g02-race.log,g02-cli-transfer.log}. Sandbox socket bị EPERM; test readiness đã sửa báo lỗi hữu hạn thay vì treo, run hợp lệ dùng quyền localhost UID thường. Không có số liệu benchmark.
- Read set tài liệu trước cập nhật hướng dẫn: README.md, START_HERE.md, docs/00-INDEX.md và docs/CLI_CONTRACT.md; đã đồng bộ trạng thái P1/P2, lệnh chạy một resource và giới hạn output hiện tại. Tệp hồ sơ/hướng dẫn thay đổi: docs/ACCEPTANCE_RESULTS.md, docs/AI_USAGE.md, docs/00-INDEX.md, docs/CLI_CONTRACT.md, README.md, START_HERE.md, .codex/TASK.md; giữ evidence P0. `git diff --check` và gofmt check PASS. Bước tiếp theo chính xác: người dùng human-review P1/P2 và G01/G02; chỉ bắt đầu P3 khi được cho phép rõ ràng.
- Final G02 rerun sau sửa tên/semantics `elapsed_ms`: `make build` exit 0, `make test` exit 0, CLI localhost 1024 byte/hash true exit 0, CA lạ exit 1, server SIGTERM exit 0; log final đã thay bản trước. Detailed parser/integration test log có seed fuzz và negative tests; race suite exit 0 trước thay đổi chỉ liên quan định dạng output CLI. Không chạy network benchmark hoặc tự tạo results CSV.

Cập nhật: 2026-09-30 UTC
Phạm vi người dùng cho phép ở checkpoint lịch sử này: **chỉ P0 và G00**, không bắt đầu P1, không commit tự động.
Trạng thái: **P0 hoàn tất / G00 PASS / dừng chờ review và cho phép phase tiếp theo**.
Bước tiếp theo chính xác: người dùng review hồ sơ/diff P0; chỉ bắt đầu P1 khi có yêu cầu rõ ràng. Không còn blocker của G00.

## Đã đọc và inspect trước khi sửa code

- AGENTS.md, docs/00-INDEX.md, TASK; CONTEXT_AND_DECISIONS, IMPLEMENTATION_PLAN (quy tắc/bản đồ/P0), CLI_CONTRACT, DEMO_SPEC, VERSIONS, ACCEPTANCE, PROTOCOL, METRICS_AND_RESULTS, NETWORK_AND_BENCHMARK (đặc biệt môi trường/đặc quyền), AI_USAGE. Đọc lại phần liên quan khi output kết hợp bị cắt; cuối lượt đối chiếu ACCEPTANCE và TRACEABILITY.
- Repo sạch tại commit `7e54ad654b14b8eb38b0db369203df4d34f003d7`, chỉ có handoff/config/schema; không có code/tests/Go module. Bảo toàn baseline người dùng đã chỉnh sau migration, không khôi phục file đã xóa.
- Go ban đầu không có trong PATH. Ubuntu 26.04.1 LTS / kernel 6.18.40.1-microsoft-standard-WSL2, UID 1000, 2 CPU logic, RAM 3053154304 bytes, swap 2147483648 bytes. Repo ở filesystem Linux native. Host Windows 11 và WSL app 3.0.1.0 vẫn là thông tin người dùng cung cấp; chưa truy vấn lại Windows CLI.
- Có Git 2.53.0, make 4.4.1, OpenSSL 3.5.5, ip/tc 6.19.0, tcpdump 4.99.6, ethtool 6.19, Python 3.14.4. sch_netem/ifb/act_mirred hiện diện; không suy ra primitive probe hoặc G07/G08 đã đạt.

## Đã triển khai trong P0

- Go 1.27.1 cài local `.tools/go1.27.1` sau khi kiểm SHA-256 official archive; quic-go v0.63.0 pin trong go.mod/go.sum, minimum Go 1.26.0 được xác minh từ tag. Không root build/download, không sửa Go hệ thống.
- Ba mains server/client/bench dùng internal/cli; help/version hoạt động, input lỗi trả 2, thao tác chưa có trả 1/not implemented. Không listener/readiness/trial/schedule/merge/result success giả.
- internal/config đọc workload/scenario chung, giới hạn JSON/memory/numeric và kiểm input; chưa sinh workload/hash P1.
- internal/tlsconfig dùng trust explicit, TLS1.3 và ALPN quicbench/1. Script cert tạo local EC P-256, SAN theo SPEC, key 0600, hạn 30 ngày, chống ghi đè khi chưa --force.
- Make build/test/test-race/certs/doctor. Doctor chỉ đọc không root; probe mạng tách script đặc quyền, chỉ tài nguyên tạm riêng và cleanup. Lượt agent bị chặn sudo; người dùng sau đó chạy thành công probe trong WSL2, đã đối chiếu log để đóng G00.
- Tests config/CLI/TLS và compile-only API đúng tag; ghi qlogwriter.Trace, NextConnection và Reno default từ source vào VERSIONS. Không thực thi QUIC/0-RTT.
- Quyết định refinement D15 ghi CONTEXT; đồng bộ CLI/PLAN/VERSIONS/README/INDEX/START_HERE/AI_USAGE/ACCEPTANCE và bảng evidence mới.

## Lệnh và kết quả thực

| Lệnh / kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| sha256sum archive; go version; go mod verify; go list -m all | PASS, exit 0; module checksums hợp lệ | docs/evidence/p0/toolchain.json, modules*.txt |
| make build | PASS, exit 0; đủ ba binaries | docs/evidence/p0/g00-commands.log |
| make test | PASS, exit 0; CLI/config/TLS/API tests | docs/evidence/p0/tests.log |
| --help / --version cả ba binaries | PASS, exit 0; commit/dirty/Go/quic-go hiện đúng | g00-commands.log |
| Input mặc định hợp lệ chưa triển khai / input lỗi | PASS: exit 1 / 2 đúng hợp đồng | g00-commands.log và tests.log |
| make certs; openssl verify cả 3 SAN; stat key | PASS; SAN đúng, key 0600; sai hostname bị reject như mong đợi | g00-commands.log; tests.log có negative trust/overwrite |
| make doctor trong sandbox | BLOCKED: netlink permission, doctor 3 / Make 2 | docs/evidence/p0/doctor.txt |
| make doctor ngoài sandbox, UID thường | PASS inventory, exit 0 | docs/evidence/p0/doctor-host.txt |
| sudo -n bash scripts/preflight-network.sh ngoài sandbox | BLOCKED: sudo cần xác thực tương tác, exit 1 trước khi script chạy | docs/evidence/p0/permission-attempts.txt |
| bash -n scripts/*.sh; git diff --check | PASS, exit 0 | Kiểm trực tiếp trong phiên; diff/status review |

G00-toolchain/build/help/input/cert/API/inventory và network-primitives PASS; **G00 tổng thể PASS**. Các lần BLOCKED trong bảng là lịch sử thử trong môi trường agent, không còn là blocker nghiệm thu. Không có gate FAIL ngoài các negative test có exit lỗi đúng kỳ vọng. G01–G12 NOT_RUN. Chưa chạy test-race vì P0 chưa có app concurrency; target sẵn cho phase phù hợp. Không có benchmark result paths: evidence/p0 chỉ là logs kiểm tra P0.

## Đóng hồ sơ P0 sau probe của người dùng

- Đã đọc lại AGENTS/INDEX/TASK, G00 trong PLAN/ACCEPTANCE/ACCEPTANCE_RESULTS, NETWORK§1, script probe, docs hiện hành và evidence trước khi sửa trạng thái. Không sửa code hay chạy lại các gate đã đạt.
- Log nguồn: results/p0-review/network-probe.log, UTC 2026-09-30T04:48:25Z, namespace qp0-27755-17396. Có netem 50ms, mirred redirect đến ifb0 và PASS sau bước xóa namespace. Người dùng xác nhận đã chạy thành công.
- Đã lưu bản chuẩn hóa tại docs/evidence/p0/network-probe.log; provenance/hash log gốc/bản lưu/script ở network-probe-provenance.json. Numeric exit code không được capture riêng; không gán exit 0 giả. Control flow set -e và PASS sau cleanup corroborate kết quả thành công.
- G00-network-primitives PASS; không suy ra traffic/RTT/rate hoặc cleanup khi interrupt đã được kiểm chứng. G07/G08 vẫn NOT_RUN.
- Giữ nguyên permission-attempts.txt, doctor.txt và các log build/test trước đó. Agent không tự nhận đã chạy probe có sudo, không ghi rằng người dùng đã review toàn bộ code.
- Đồng bộ ACCEPTANCE_RESULTS, VERSIONS, README, START_HERE, CONTEXT D15, AI_USAGE và evidence index. Kiểm hash/đối chiếu log, git diff --check và review diff hồ sơ; không có application code thay đổi trong lượt đóng hồ sơ.
- Lệnh tái lập: make build; make test; make doctor; sudo bash scripts/preflight-network.sh. Chi tiết lưu log và cài toolchain ở README/ACCEPTANCE_RESULTS. Không cần chạy lại để đóng hồ sơ lần này.

## Tệp thay đổi và review

- Mới: go.mod/go.sum, Makefile, cmd/{server,client,bench}/main.go; internal/{cli,config,tlsconfig}; tests/api/quic_test.go; scripts/{gen-cert,doctor,preflight-network}.sh; docs/ACCEPTANCE_RESULTS.md và docs/evidence/p0/.
- Sửa: .gitignore, README, START_HERE, TASK; docs/00-INDEX, ACCEPTANCE, AI_USAGE, CLI_CONTRACT, CONTEXT_AND_DECISIONS, IMPLEMENTATION_PLAN, VERSIONS.
- Không đổi configs, schemas, originals hoặc provenance/source manifests. .tools/bin/certs/results local được gitignore; không đưa key hoặc benchmark giả vào diff. Không tạo commit.
- Self-review và điểm cần duyệt ở docs/ACCEPTANCE_RESULTS.md. Bản diff bàn giao gồm cả file mới (git diff mặc định chưa gồm untracked); chưa có human review.

## Lịch sử và phạm vi còn lại

Handoff 2026-09-28 chọn Ubuntu VM; D13 ngày 2026-09-30 thay bằng Ubuntu WSL2 sau preflight người dùng cung cấp. D14 đổi mặc định thành human-gated. Migration tài liệu đã hoàn thành; lượt này chỉ triển khai P0 được cấp quyền.

Checkpoint lịch sử P0: hoàn tất, G00 PASS, dừng review. Trạng thái mới nhất P1/P2 ở đầu file; không tự mở rộng sang P3.
