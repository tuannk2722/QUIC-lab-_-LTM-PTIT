# Tiến độ công việc

Cập nhật: 2026-09-30 UTC
Phạm vi người dùng cho phép: **chỉ P0 và G00**, không bắt đầu P1, không commit tự động.
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

P0: hoàn tất, G00 PASS, dừng review. P1–P12: NOT_STARTED. Không tự mở rộng scope để giải quyết phase sau.
