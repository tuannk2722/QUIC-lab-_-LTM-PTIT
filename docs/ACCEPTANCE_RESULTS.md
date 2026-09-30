# Kết quả nghiệm thu — P0/G00 đến P3/G03

Ngày: 2026-09-30 UTC. Baseline: `7e54ad654b14b8eb38b0db369203df4d34f003d7`. Người dùng đã human-review/approve P0/G00, cho phép P1→G01→P2→G02 tuần tự, rồi yêu cầu riêng P3/G03. Môi trường: Ubuntu 26.04.1 LTS trong WSL2, UID 1000.

**P0/G00 PASS; P1/G01 PASS; P2/G02 PASS; P3/G03 PASS.** Phần capability G00 được đóng bằng log probe do người dùng chạy trong WSL2 lúc `2026-09-30T04:48:25Z`. Agent đã đối chiếu output và script, không tự nhận là người thực thi. P3 chờ human review; chưa có xác nhận review P1/P2.

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
| G01-fixture/determinism | PASS | `go test -v ./internal/workload` với local Go/cache | Fixture ID1 4 byte = `01 02 03 04`, SHA-256 cố định; bulk 6×1MiB và handshake 1×1KiB có cùng bytes/hash giữa hai lần generate | [tests](evidence/p1/g01-workload-tests.log), [manifest](evidence/p1/workload-manifest.json) | Không |
| G01-bounds/store | PASS | `make test`; `go test -race ./internal/workload` | Count/size/chunk/total overflow reject trước allocate; concurrent readers trên cùng immutable Store; toàn suite và race exit 0 | [suite](evidence/p1/g01-suite.log), [race](evidence/p1/g01-race.log) | Runtime TCP/QUIC chung store sẽ được xác minh sau khi QUIC có ở G04 |
| G02-QB01 parser | PASS | `go test -v -count=1 ./internal/protocol` | Golden header 24 byte; REQUEST/META/ERROR roundtrip; partial read/write, coalesced frames, no-progress writer, malformed/truncated/oversize header, response state/hash; fuzz seed#0–2 đạt | [detailed tests](evidence/p2/g02-detailed-tests.log) | Không chạy long fuzz campaign; seed cases theo G02 |
| G02-TCP/TLS localhost | PASS | `make test`; `go test -v -count=1 ./tests/integration`; `make test-race` | TLS1.3/ALPN transfer 1×1024 byte đúng SHA-256; untrusted CA fail; truncated frame, bad length, timeout và cancel kết thúc hữu hạn; toàn suite/race exit 0 | [suite](evidence/p2/g02-suite.log), [detailed tests](evidence/p2/g02-detailed-tests.log), [race](evidence/p2/g02-race.log) | Localhost chỉ kiểm correctness |
| G02-CLI transfer | PASS | `make build`; `bin/server --transport=tcp --profile=handshake --listen=127.0.0.1:14433` + `bin/client` tương ứng; CA khác | Server ready; client exit 0 với 1024 byte/checksum true; CA khác exit 1/x509; server SIGTERM exit 0 | [build](evidence/p2/g02-build.log), [CLI](evidence/p2/g02-cli-transfer.log) | Canonical result files/metrics đầy đủ thuộc P5/P6 |
| G03-batch/scheduler | PASS | `go test -count=1 -v ./internal/protocol ./internal/transport/tcp` | Batch reject duplicate/count/chunk sai; transcript 6 resource có META 1..6, DATA xen vòng 0/2/4, FIN sau DATA cuối; không ghi trọn file theo ID | [detailed tests](evidence/p3/g03-detailed-tests.log) | Transcript là QB01 frame order, không suy ra TCP packet order |
| G03-TCP multiplex | PASS | `make test`; `go test -count=1 -v ./tests/integration`; `make test-race` | Localhost thực: 1 accepted TLS connection/6 resources ×1 MiB, đủ 6 hash; batch thiếu timeout có ERROR 6, duplicate ERROR 3, cancel giải phóng handler; suite/race exit 0 | [suite](evidence/p3/g03-suite.log), [detailed tests](evidence/p3/g03-detailed-tests.log), [race](evidence/p3/g03-race.log) | Localhost chỉ kiểm correctness; không phải benchmark |
| G03-CLI bulk | PASS | `make build`; `bin/server --transport=tcp --profile=bulk --listen=127.0.0.1:14435`; `bin/client --transport=tcp --profile=bulk --addr=127.0.0.1:14435 --server-name=localhost --format=json` | Ba binaries build exit 0; client/server exit 0; JSON 6 rows, 6,291,456 bytes, 6 checksum true; server SIGTERM exit 0 | [build](evidence/p3/g03-build.log), [CLI transfer](evidence/p3/g03-cli-transfer.log) | `elapsed_ms` ở stdout chỉ thông tin localhost; canonical results thuộc P5/P6 |
| G04–G12 | NOT_RUN | Chưa chạy | Chưa có QUIC runtime, topology G07/G08, benchmark, 0-RTT hoặc PCAP/qlog thực | Không có dataset hiệu năng | Chờ phase riêng |

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

## Review thay đổi P0 (lịch sử tại thời điểm P0)

- go.mod/go.sum và Makefile: pin exact dependency, bắt đúng Go, GOTOOLCHAIN=local; cache/toolchain local gitignored. Build/test unprivileged và không tự chạy benchmark.
- internal/config: config tối đa 1 MiB/độ sâu 32; reject duplicate/unknown/trailing, kiểm count/size/total trước workload allocation; không có resource generator P1.
- internal/cli và ba mains: thống nhất flags/defaults, lỗi input 2, chưa triển khai 1; help/version 0. Không tạo readiness hoặc result success giả.
- internal/tlsconfig, gen-cert: trust rõ ràng, TLS1.3/ALPN, SAN, private key 0600; tests âm cho sai tên/CA và overwrite. Cert/key thật chỉ local, không đưa vào diff.
- doctor/probe: inventory và đặc quyền tách riêng; người dùng đã chạy thành công đường tạo/xóa tài nguyên bình thường. Dòng PASS được in sau lệnh xóa namespace dưới set -e; không suy ra cleanup khi lỗi/interrupt hoặc topology G07 đã được kiểm chứng.
- API pin: compile/source checks không tương đương network test. Runtime handshake/ticket/rejection/qlog/viewer còn để đúng phase sau.

Đây là self-review của agent; người dùng đã chạy/xác nhận probe, chưa có xác nhận review toàn bộ code. Không phát hiện thay đổi ngoài scope P0 trong code. Không chạy test-race vì P0 không có app concurrency; target sẵn cho phase phù hợp. Originals, source manifests, configs và result schema giữ nguyên; không commit. Diff đầy đủ (kể cả file mới) được cung cấp khi bàn giao, không chỉ git diff mặc định vốn bỏ qua untracked files.
