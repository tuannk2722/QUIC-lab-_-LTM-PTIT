# QUIC Performance Lab

T03 — QUIC Protocol Implementation and Performance, môn Lập trình mạng, PTIT.

**Trạng thái hiện tại:** P0/G00 đến P3/G03 PASS; P3 chờ human review, P1/P2 chưa có xác nhận review. Có workload deterministic, QB01 codec và TCP/TLS multiplex 6 resource trên một connection. Chưa có QUIC runtime, network testbed hoặc kết quả benchmark. Đọc [START_HERE.md](START_HERE.md) để dùng trong IDE.

Thiết kế: cùng bộ resource trong RAM được phục vụ bởi TCP/TLS multiplex và raw QUIC trên TCP/UDP 4433. Client chạy trong Ubuntu dưới WSL2 trên Windows 11 qua hai namespace có network impairment. Số liệu từ client được lưu theo run và resource; qlog và packet capture phục vụ giải thích cơ chế.

[Đặc tả](docs/DEMO_SPEC.md) · [Kế hoạch triển khai](docs/IMPLEMENTATION_PLAN.md) · [Nghiệm thu](docs/ACCEPTANCE.md) · [Kịch bản demo](docs/DEMO_SCRIPT.md)

Repo phải nằm trong filesystem Linux native, ưu tiên `/home/<user>/...`, không `/mnt/c/...` hoặc `/mnt/d/...`. Mở Windows VS Code bằng Remote WSL, workspace `WSL: Ubuntu`. Implementation mặc định human-gated: chỉ phase được người dùng cho phép, chạy gate rồi cập nhật TASK và dừng review. P3/G03 đã được cho phép và chạy xong; dừng để review trước P4. Xem [bằng chứng acceptance](docs/ACCEPTANCE_RESULTS.md).

## Tái lập P0 (chạy bên trong Ubuntu WSL2)

Cần bash, curl, tar, sha256sum, make, OpenSSL, Python 3; preflight dùng iproute2, tcpdump, ethtool. Máy hiện tại đã có các công cụ này. Tải Go exact version và kiểm checksum (fresh checkout chưa có `.tools/go1.27.1`):

```bash
curl -fL https://go.dev/dl/go1.27.1.linux-amd64.tar.gz -o /tmp/quic-lab-go1.27.1.tar.gz
echo '63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445  /tmp/quic-lab-go1.27.1.tar.gz' | sha256sum -c -
mkdir -p .tools/go1.27.1
tar -xzf /tmp/quic-lab-go1.27.1.tar.gz -C .tools/go1.27.1 --strip-components=1
export PATH="$PWD/.tools/go1.27.1/bin:$PATH"
export GOTOOLCHAIN=local GOPATH="$PWD/.tools/gopath" GOCACHE="$PWD/.tools/gocache"
go mod download
go mod verify
make build
make test
make certs
make doctor
bin/server --help
bin/client --version
bin/bench --help
```

Makefile tự chọn Go local nếu có, nếu không dùng PATH và kiểm đúng version. `make test-race` cần C compiler. `.tools/`, `bin/`, private keys/certs và results được gitignore. P0 compile tests import raw quic-go, không dùng HTTP/3.

`make certs` tạo cert local hạn 30 ngày, SAN localhost/127.0.0.1/10.10.0.2, key 0600; từ chối ghi đè. Chỉ khi chủ động thay identity và đã dừng mọi server, dùng `make certs CERT_FORCE=--force`. Test tạo identity riêng trong thư mục tạm, không sửa cert đang dùng.

Các lệnh ngoài phạm vi P3 (`bin/bench`, QUIC) còn trả **exit 1 / not implemented**. Input/config không hợp lệ trả **2**. `--help`/`--version` trả 0. Defaults workload/scenario/timeouts được đọc từ configs; `--profiles` và `--scenarios` cho phép chọn tệp rõ ràng.

`make doctor` chỉ inventory, không tạo namespace hoặc cấp quyền cho Go. Nếu sandbox chặn netlink, chạy lệnh ở terminal Ubuntu WSL bình thường. Để tái lập primitive preflight (đã PASS trong hồ sơ P0), chạy:

```bash
mkdir -p results/p0-review
set -o pipefail
sudo bash scripts/preflight-network.sh 2>&1 | tee results/p0-review/network-probe.log
```

Probe dùng một namespace tạm có tên riêng, veth + IFB/mirred/netem 50 ms bên trong và tự cleanup; không dùng qclient/qserver chính, không đo traffic/RTT và không thay G07/G08. Nếu cleanup báo lỗi, chỉ xử lý tên namespace được log; không xóa namespace không rõ chủ sở hữu. Log lần chạy thành công đã lưu tại `docs/evidence/p0/network-probe.log`.

Bằng chứng P0 lưu tại `docs/evidence/p0/`; đây là build/preflight/test logs, không phải benchmark results.

## P1/P2: workload và TCP/TLS một resource

Trong Ubuntu WSL2, sau `make build`, `make test`, `make test-race` và `make certs` nếu chưa có cert, chạy hai terminal từ repo root:

```bash
# Terminal 1
bin/server --transport=tcp --profile=handshake --listen=127.0.0.1:14433
# Terminal 2
bin/client --transport=tcp --profile=handshake --addr=127.0.0.1:14433 --server-name=localhost --format=json
```

Client thành công chỉ khi nhận đủ 1.024 byte, FIN và hash đúng. Dừng server bằng Ctrl+C. Test G02 cũng kiểm CA sai, frame lỗi và timeout qua localhost thực. JSON trên stdout là kết quả P2 tối thiểu; canonical result files/metrics và benchmark thuộc phase sau. Bằng chứng ở `docs/evidence/p1/`, `docs/evidence/p2/` và [ACCEPTANCE_RESULTS](docs/ACCEPTANCE_RESULTS.md). Không suy ra hiệu năng từ localhost.

## P3: TCP/TLS multiplex 6 resource

Từ repo root, sau `make build` và `make certs` nếu chưa có cert:

```bash
# Terminal 1
bin/server --transport=tcp --profile=bulk --listen=127.0.0.1:14435
# Terminal 2
bin/client --transport=tcp --profile=bulk --addr=127.0.0.1:14435 --server-name=localhost --format=json
```

Client gửi đủ 6 REQUEST trước khi nhận response; server chờ batch đủ rồi phát META 1..6 và DATA round-robin trên một TLS connection. Kết quả JSON tối thiểu có 6 resource, tổng 6.291.456 bytes và `checksum_ok=true` cho từng resource. `make test`/`make test-race` kiểm batch timeout, cancel, transcript frame và connection count. Bằng chứng ở [G03](docs/ACCEPTANCE_RESULTS.md). Đây là localhost correctness; metric/CSV chuẩn và so sánh network thuộc các phase sau.

## Hợp đồng README sau triển khai đầy đủ

Agent phải thay mục này bằng các bước **đã kiểm tra thực tế**, giữ lại lịch sử trạng thái nếu hữu ích:

1. Phiên bản OS/kernel, Go, quic-go và package hệ thống cần cài.
2. Clone/mở repo; build; tạo certificate; unit/integration tests.
3. Setup topology; server background và readiness; client TCP/QUIC.
4. Chạy từng demo và benchmark; tạo báo cáo/biểu đồ.
5. Xem CSV, qlog, PCAP; cách giải mã traffic demo nếu cần.
6. Dừng server, clear-netem, teardown; xử lý lỗi phổ biến và môi trường thiếu quyền.
7. Chỉ rõ lệnh chạy ở host Windows hay bên trong Ubuntu WSL2; mọi build/test/network/benchmark chạy trong Ubuntu WSL2.
8. Liên kết provenance, disclosure AI và giới hạn kết luận.

Hiện có targets build/test/test-race/certs/doctor. Các targets setup-network, demo, benchmark, analyze và cleanup trong CLI contract vẫn để các phase sau.
