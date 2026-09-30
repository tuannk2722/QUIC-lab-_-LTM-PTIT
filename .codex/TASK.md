# Tiến độ công việc

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
