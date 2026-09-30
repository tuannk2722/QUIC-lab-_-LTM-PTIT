# Kết quả nghiệm thu — P0 / G00

Ngày: 2026-09-30 UTC. Baseline: `7e54ad654b14b8eb38b0db369203df4d34f003d7`, working tree có thay đổi P0 chưa commit. Phạm vi được người dùng cho phép: **chỉ P0**, không P1. Môi trường: Ubuntu 26.04.1 LTS trong WSL2, UID 1000.

**P0 hoàn tất; G00 tổng thể: PASS.** Các kiểm tra độc lập đã đạt; phần capability được đóng bằng log probe do người dùng chạy trong WSL2 lúc `2026-09-30T04:48:25Z`. Agent đã đối chiếu output và script, không chạy lại hoặc tự nhận là người thực thi. Không mở rộng sang P1.

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
| G00-network-primitives | PASS | Người dùng: sudo bash scripts/preflight-network.sh | Log có netem 50ms, mirred redirect→ifb0 và PASS sau xóa namespace; người dùng xác nhận chạy thành công. Không có numeric exit code ghi riêng trong log | [probe](evidence/p0/network-probe.log), [provenance/hash](evidence/p0/network-probe-provenance.json) | Không; G07/G08 vẫn NOT_RUN |
| G01–G12 | NOT_RUN | Không chạy | Không workload P1, transfer, topology G07/G08, benchmark, 0-RTT hoặc PCAP/qlog thực | Không có dataset hiệu năng | Chờ cấp quyền theo từng phase |

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

Người dùng nhập mật khẩu sudo trong terminal của mình. Agent không nhận/ghi mật khẩu. Probe tạo/xóa namespace tạm riêng, veth/IFB, ingress redirect và netem 50ms; không tạo qclient/qserver hoặc chạy app. Log lần chạy nêu trên đã được review và đóng capability G00; không pass G07/G08. Các lỗi sudo/netlink trước đây vẫn giữ trong evidence làm lịch sử, không còn là blocker hiện tại của G00. P1 chỉ bắt đầu khi được người dùng cho phép rõ ràng.

## Review thay đổi P0

- go.mod/go.sum và Makefile: pin exact dependency, bắt đúng Go, GOTOOLCHAIN=local; cache/toolchain local gitignored. Build/test unprivileged và không tự chạy benchmark.
- internal/config: config tối đa 1 MiB/độ sâu 32; reject duplicate/unknown/trailing, kiểm count/size/total trước workload allocation; không có resource generator P1.
- internal/cli và ba mains: thống nhất flags/defaults, lỗi input 2, chưa triển khai 1; help/version 0. Không tạo readiness hoặc result success giả.
- internal/tlsconfig, gen-cert: trust rõ ràng, TLS1.3/ALPN, SAN, private key 0600; tests âm cho sai tên/CA và overwrite. Cert/key thật chỉ local, không đưa vào diff.
- doctor/probe: inventory và đặc quyền tách riêng; người dùng đã chạy thành công đường tạo/xóa tài nguyên bình thường. Dòng PASS được in sau lệnh xóa namespace dưới set -e; không suy ra cleanup khi lỗi/interrupt hoặc topology G07 đã được kiểm chứng.
- API pin: compile/source checks không tương đương network test. Runtime handshake/ticket/rejection/qlog/viewer còn để đúng phase sau.

Đây là self-review của agent; người dùng đã chạy/xác nhận probe, chưa có xác nhận review toàn bộ code. Không phát hiện thay đổi ngoài scope P0 trong code. Không chạy test-race vì P0 không có app concurrency; target sẵn cho phase phù hợp. Originals, source manifests, configs và result schema giữ nguyên; không commit. Diff đầy đủ (kể cả file mới) được cung cấp khi bàn giao, không chỉ git diff mặc định vốn bỏ qua untracked files.
