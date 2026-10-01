# QUIC Performance Lab

T03 — QUIC Protocol Implementation and Performance, môn Lập trình mạng, PTIT.

**Trạng thái hiện tại:** P0/G00 đến P6/G06 PASS. G07 **FAIL trong lần chạy đầu 2026-10-01**: topology và ping đạt, nhưng IFB driver tạo thêm hai interface host; runner dừng trước TCP/QUIC transfer. Setup đã được sửa, cần khôi phục host IFB và chạy lại G07 thực. G08 impairment và benchmark chưa triển khai. Xem [ACCEPTANCE_RESULTS](docs/ACCEPTANCE_RESULTS.md) và [START_HERE.md](START_HERE.md).

Thiết kế: cùng bộ resource trong RAM được phục vụ bởi TCP/TLS trên TCP và raw QUIC trên UDP cùng số port 4433. P7 chuẩn bị hai namespace trong Ubuntu WSL2; impairment qua IFB, benchmark và qlog/packet capture thuộc các phase sau.

[Đặc tả](docs/DEMO_SPEC.md) · [Kế hoạch triển khai](docs/IMPLEMENTATION_PLAN.md) · [Nghiệm thu](docs/ACCEPTANCE.md) · [Kịch bản demo](docs/DEMO_SCRIPT.md)

Repo phải nằm trong filesystem Linux native, ưu tiên `/home/<user>/...`, không `/mnt/c/...` hoặc `/mnt/d/...`. Mở Windows VS Code bằng Remote WSL, workspace `WSL: Ubuntu`. Implementation mặc định human-gated: chỉ phase được người dùng cho phép, chạy gate rồi cập nhật TASK và dừng review. Người dùng đã cho phép P7/G07; xem [bằng chứng acceptance](docs/ACCEPTANCE_RESULTS.md) để biết trạng thái gate mới nhất.

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

`bin/bench` và client `--mode=resumed|early` còn trả **exit 1 / not implemented**; cold TCP/QUIC được hỗ trợ. Input/config không hợp lệ trả **2**. `--help`/`--version` trả 0. Defaults workload/scenario/timeouts được đọc từ configs; `--profiles` và `--scenarios` cho phép chọn tệp rõ ràng.

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

Client thành công chỉ khi nhận đủ 1.024 byte, FIN và hash đúng. Dừng server bằng Ctrl+C. Test G02 cũng kiểm CA sai, frame lỗi và timeout qua localhost thực. Output P2 lúc đó là tối thiểu; P5/P6 hiện đã thêm metrics và result files. Bằng chứng ở `docs/evidence/p1/`, `docs/evidence/p2/` và [ACCEPTANCE_RESULTS](docs/ACCEPTANCE_RESULTS.md). Không suy ra hiệu năng từ localhost.

## P3: TCP/TLS multiplex 6 resource

Từ repo root, sau `make build` và `make certs` nếu chưa có cert:

```bash
# Terminal 1
bin/server --transport=tcp --profile=bulk --listen=127.0.0.1:14435
# Terminal 2
bin/client --transport=tcp --profile=bulk --addr=127.0.0.1:14435 --server-name=localhost --format=json
```

Client gửi đủ 6 REQUEST trước khi nhận response; server chờ batch đủ rồi phát META 1..6 và DATA round-robin trên một TLS connection. Kết quả JSON có 6 resource, tổng 6.291.456 bytes và `checksum_ok=true` cho từng resource. `make test`/`make test-race` kiểm batch timeout, cancel, transcript frame và connection count. Bằng chứng ở [G03](docs/ACCEPTANCE_RESULTS.md). Đây là localhost correctness; P5/P6 đã thêm metric/CSV, so sánh network thuộc các phase sau.

## P4: TCP/TLS và raw QUIC cold trên cùng port

Từ repo root trong Ubuntu WSL2, sau `make build` và `make certs` nếu chưa có cert, chạy hai terminal:

```bash
# Terminal 1: một process, TCP và UDP cùng số port 4433
mkdir -p results
bin/server --transport=both --profile=bulk --listen=127.0.0.1:4433 --ready-file=results/p4-ready.txt
# Terminal 2: hai trial cold riêng trên hai transport
bin/client --transport=tcp --mode=cold --profile=bulk --addr=127.0.0.1:4433 --server-name=localhost --format=json
bin/client --transport=quic --mode=cold --profile=bulk --addr=127.0.0.1:4433 --server-name=localhost --format=json
```

Server công bố ready file atomically sau khi cả hai listeners đã bind; từ chối ghi đè marker đã có và xóa marker của mình khi dừng bình thường. Cả hai listeners dùng chung certificate và một RAM workload store, với tối đa 8 connections đang xử lý tổng cộng. Mỗi QUIC resource dùng một bidirectional stream; JSON tối thiểu ghi `transport_stream_id` thực bên cạnh `resource_id`, bytes và checksum. Client QUIC gửi các REQUEST trên nhiều stream rồi nhận response độc lập, dùng cùng QB01 và kiểm đủ FIN/EOF/hash. QUIC v1 cho phép server nhận 64 bidirectional streams, client từ chối stream do server tự mở; hai phía tắt incoming unidirectional streams. Receive credits ban đầu/tối đa là 512 KiB/2 MiB mỗi stream và 2 MiB/16 MiB mỗi connection.

Đây là đường truyền cold và kiểm chức năng trên localhost, chưa phải benchmark. `--allow-0rtt`, các mode resumed/early, IFB impairment và network benchmark thuộc các phase sau; topology namespace P7 được hướng dẫn bên dưới. Không suy ra performance hoặc G07/G08 từ output localhost; trạng thái G04 được ghi tại [ACCEPTANCE_RESULTS](docs/ACCEPTANCE_RESULTS.md).

## P5/P6: metrics và canonical result files

Cold client tự tạo thư mục mới `results/<experiment_id>/` sau mỗi lần chạy; `--out=DIR`, `--experiment-id=ID`, `--run-id=ID` cho phép đặt rõ. Trong đó có `raw/<run_id>.json`, `runs.csv`, `streams.csv`. Trial thất bại sau khi bắt đầu vẫn ghi run/resource rows và trả exit 1; nếu ghi file lỗi, command cũng trả exit 1. Mốc chưa xảy ra là `null` trong JSON và ô rỗng trong CSV. Kết quả G06 thật, gồm TCP/QUIC thành công và TLS trust failure, nằm ở [evidence P6](docs/evidence/p6/actual/); chỉ là correctness trên localhost.

```bash
make build
make test
make test-race
bash docs/evidence/p6/run-g06.sh
# Script in ra results_dir mới; ví dụ:
python3 analysis/validate.py results/<p6-g06-dir>/tcp_success
python3 analysis/validate.py results/<p6-g06-dir>/quic_success
python3 analysis/validate.py results/<p6-g06-dir>/tcp_failure
```

`docs/REPORT.md` hiện là template, chưa có manifest thí nghiệm đầy đủ, schedule, summary/plots hay benchmark. `bin/bench` và resumption/0-RTT vẫn thuộc phase sau.

## P7: topology namespace và tách quyền

P7 có `qclient` (`10.10.0.1/24`) và `qserver` (`10.10.0.2/24`) nối bằng veth `eth0`, MTU 1500; `lo` và `ifb0` được đưa lên. Ownership marker root-owned ở `/run/quic-performance-lab/topology-v1` gắn người gọi sudo với identity của hai namespace. Setup lặp lại được khi topology và marker khớp; collision không có marker bị từ chối. Setup nạp IFB với `numifbs=0` để tránh tạo IFB mặc định trên host; sửa này chưa qua G07 rerun. `ifb0` ở P7 chưa gắn ingress redirect hoặc netem: impairment chính và xác minh RTT/counter thuộc P8/G08.

Các lệnh sau chạy từ repo root trong terminal Ubuntu WSL2 của người dùng thường. Nếu chưa có `certs/server.crt` và `certs/server.key`, chạy `make certs` trước. Terminal 1:

```bash
make build
mkdir -p results
make setup-network
make server PROFILE=bulk
```

`make server` chạy foreground trong `qserver` và build bằng UID thường trước khi vào namespace. Terminal 2, khi server đã in readiness:

```bash
sudo bash scripts/run-in-netns.sh qclient -- "$PWD/bin/client" --transport=tcp --mode=cold --profile=bulk --addr=10.10.0.2:4433 --server-name=10.10.0.2 --ca="$PWD/certs/server.crt" --format=json
sudo bash scripts/run-in-netns.sh qclient -- "$PWD/bin/client" --transport=quic --mode=cold --profile=bulk --addr=10.10.0.2:4433 --server-name=10.10.0.2 --ca="$PWD/certs/server.crt" --format=json
```

Wrapper chỉ vào namespace đã được lab sở hữu và dùng `setpriv` để chạy server/client dưới UID/GID của người gọi sudo; các thư mục kết quả do client tạo thuộc user thường. Sau transfer, nhấn Ctrl+C ở terminal server, rồi chạy trong terminal 2:

```bash
make clean-network
```

Teardown từ chối xóa namespace còn PID; không xóa tên trùng nhưng không có marker sở hữu. Raw JSON/CSV của client hiện vẫn ghi `network_profile=loopback-test` theo P6; dùng chúng để kiểm correctness, không coi là số liệu benchmark đã xác minh mạng.

Lần G07 đầu để lại hai IFB host DOWN/noop; snapshot xác nhận chúng không có ở baseline. Trước khi rerun, chạy precheck không đặc quyền rồi dọn đúng hai thiết bị đã xác minh bằng sudo tương tác, giữ log riêng:

```bash
bash scripts/network/restore-host-ifb.sh --check-only results/p7-g07-JqV32x/host-state
set -o pipefail
sudo bash scripts/network/restore-host-ifb.sh results/p7-g07-JqV32x/host-state 2>&1 | tee docs/evidence/p7/g07-host-recovery.log
recovery_status=${PIPESTATUS[0]}; printf 'recovery_exit=%s\n' "$recovery_status" | tee -a docs/evidence/p7/g07-host-recovery.log
```

Script từ chối nếu host đã đổi so với snapshot, IFB đang được cấu hình/sử dụng hoặc host có tc filter; kiểm lại trước từng lần xóa và hỗ trợ chạy tiếp sau khi mới xóa một IFB. Tránh thay đổi mạng host đồng thời khi recovery; script so sánh lại link/address/route với baseline sau khi xóa. Chưa có log recovery thực. Sau khi recovery exit 0, để chạy **toàn bộ G07** từ trạng thái không có `qclient`/`qserver`, giữ `results/` writable và cert đã tạo, chạy trong terminal Ubuntu WSL2:

```bash
make build
test -r certs/server.crt && test -r certs/server.key || make certs
mkdir -p results
set -o pipefail
sudo bash tests/system/run.sh 2>&1 | tee docs/evidence/p7/g07-system-rerun.log
g07_status=${PIPESTATUS[0]}; printf 'g07_exit=%s\n' "$g07_status" | tee -a docs/evidence/p7/g07-system-rerun.log
```

Runner kiểm collision, rollback lỗi giữa setup, hai vòng setup/teardown, ping hai chiều, transfer TCP/QUIC thật, UID/GID, SIGINT cleanup và so sánh host link/address/routes. Log đầu `docs/evidence/p7/g07-system.log` có `G07 FAIL` ở host-state, chưa có TCP/QUIC result. Bản sửa IFB chưa được kiểm bằng lần chạy đặc quyền; chỉ đổi G07 sang PASS sau khi rerun đạt hết các bước và review artifacts thật.

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

Hiện có targets build/test/test-race/certs/doctor và P7 setup-network/server/clean-network. Các targets demo, benchmark, analyze và clear-netem trong CLI contract vẫn để các phase sau.
