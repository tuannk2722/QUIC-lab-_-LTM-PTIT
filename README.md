# QUIC Performance Lab

T03 — QUIC Protocol Implementation and Performance, môn Lập trình mạng, PTIT.

**Trạng thái hiện tại:** P10/G10 **PASS**. P11 early-secret export/full Go/race PASS; latest actual G11 FAIL0/23 trước topology vì reset-env PATH thiếu sbin/sysctl. D29 đã sửa PATH và exact runtime/lifecycle9 PASS. Chạy lại `bash scripts/run-g11-review.sh`; [P11 evidence/lệnh/review](docs/evidence/p11/README.md). Full decrypted packet0RTT/HOL chờ actual gate; không P12.

P9 dataset lịch sử tại `results/p9-g09-8dFdkj/main/` có main240 measured+16 warmup, 256 success/0 failure, 1536 resource rows và controlled interrupt/cleanup verified. [D24 audit](docs/evidence/audit-p7-p9/README.md) giữ nguyên các lần BLOCKED trước đây. Interactive terminal Ctrl+C qua tee từng exit141/cleanup1 còn là limitation riêng; controlled interrupt PASS không xác minh lại đường terminal đó. Xem [ACCEPTANCE_RESULTS](docs/ACCEPTANCE_RESULTS.md) và [P9 evidence](docs/evidence/p9/README.md).

Thiết kế: cùng bộ resource trong RAM được phục vụ bởi TCP/TLS trên TCP và raw QUIC trên UDP cùng số port 4433. Hai namespace chạy trong Ubuntu WSL2; P8 cấu hình impairment phía nhận qua IFB. P9 orchestrator quản lý benchmark tuần tự; P11 đã thêm qlog/progress và capture driver; actual capture gate còn BLOCKED.

[Đặc tả](docs/DEMO_SPEC.md) · [Kế hoạch triển khai](docs/IMPLEMENTATION_PLAN.md) · [Nghiệm thu](docs/ACCEPTANCE.md) · [Kịch bản demo](docs/DEMO_SCRIPT.md)

Repo phải nằm trong filesystem Linux native, ưu tiên `/home/<user>/...`, không `/mnt/c/...` hoặc `/mnt/d/...`. Mở Windows VS Code bằng Remote WSL, workspace `WSL: Ubuntu`. Implementation mặc định human-gated: chỉ phase được người dùng cho phép, chạy gate rồi cập nhật TASK và dừng review. Phạm vi được cho phép hiện tại là riêng P11/G11; xem [bằng chứng acceptance](docs/ACCEPTANCE_RESULTS.md) để biết trạng thái gate mới nhất.

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

Client hỗ trợ `--mode=cold` trên TCP/QUIC, `--mode=resumed|early` trên QUIC với `--profile=handshake`; bench hỗ trợ bulk và handshake suites. Input/config không hợp lệ trả **2**; transfer hoặc ghi results thất bại trả **1**. `--help`/`--version` trả 0. Defaults workload/scenario/timeouts được đọc từ configs; `--profiles` và `--scenarios` cho phép chọn tệp rõ ràng.

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

Các lệnh trên kiểm đường truyền cold trên localhost. P10 đã thêm `--allow-0rtt` và resumed/early theo hướng dẫn bên dưới; P7/P8/P9 cung cấp topology/IFB/network benchmark. Không suy ra performance hoặc G07/G08 từ output localhost; trạng thái G04 được ghi tại [ACCEPTANCE_RESULTS](docs/ACCEPTANCE_RESULTS.md).

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

`docs/REPORT.md` ghi trạng thái dataset; P9 sinh manifest/schedule/summary/plots/report trong thư mục experiment. Main dataset thật tại `results/p9-g09-8dFdkj/main/`; resumption/0-RTT thuộc P10.

## P7: topology namespace và tách quyền

P7 có `qclient` (`10.10.0.1/24`) và `qserver` (`10.10.0.2/24`) nối bằng veth `eth0`, MTU 1500; `lo` và `ifb0` được đưa lên. Ownership marker root-owned ở `/run/quic-performance-lab/topology-v1` gắn người gọi sudo với identity của hai namespace. Setup lặp lại được khi topology và marker khớp; collision không có marker bị từ chối. Setup nạp IFB với `numifbs=0` để tránh tạo IFB mặc định trên host; G07 rerun đã PASS. P8 gắn ingress redirect/netem khi gọi apply bên dưới.

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

G07 lần đầu FAIL vì hai IFB host được tạo khi module nạp với mặc định. Recovery và rerun đã exit 0: [log và review artifacts](docs/evidence/p7/README.md), kết quả thật `results/p7-g07-vNiIgt/`. Không cần recovery lại trong trạng thái hiện tại. G07 chỉ xác nhận topology/correctness, không thay G08.

## P8: impairment và G08

Từ repo root trong Ubuntu WSL2, setup topology rồi apply khi client/server idle:

```bash
make setup-network
make netem SCENARIO=rtt50-loss0 NETWORK_PROFILE=ingress-ifb NETEM_SEED=default
mkdir -p results/p8-inspect
make -s inspect-network > results/p8-inspect/network.json
# Server chạy foreground ở terminal khác: make server PROFILE=bulk
sudo bash scripts/run-in-netns.sh qclient -- "$PWD/bin/client" --transport=quic --mode=cold --profile=bulk --addr=10.10.0.2:4433 --server-name=10.10.0.2 --network-state="$PWD/results/p8-inspect/network.json" --out=results/p8-inspect/quic
make clear-netem
# Dừng server bằng Ctrl+C trước:
make clean-network
```

Để lưu JSON dùng trực tiếp `sudo bash scripts/network/inspect.sh | tee PATH` hoặc `make -s inspect-network > PATH` (Make thông thường echo recipe, nên dùng `-s`). Client `--network-state` yêu cầu snapshot mới trong 5 phút và đúng qclient identity; records gắn scenario/profile/seed thực với phase/trace_mode=evidence. Refresh snapshot trước mỗi trial; wrapper phải kiểm trước/sau vì file không khóa kernel trong suốt transfer. Không có flag thì giữ loopback-test/exploratory.

`make netem NETWORK_PROFILE=egress-demo` chỉ dùng minh họa; clear rồi đổi profile, không trộn vào main ingress-ifb. Offloads GSO/GRO/TSO và UDP liên quan được tắt trên veth/IFB khi có thể; option fixed/absent được ghi, option còn ON làm apply fail. Clear gỡ qdisc/filter, giữ namespace và offload OFF; teardown xóa namespace. Seed không hỗ trợ làm command nonzero; chỉ chọn `NETEM_SEED=none` có chủ ý mới ghi seed=null/disabled-explicitly, không fallback ngầm.

Chạy đầy đủ G08 từ trạng thái không có topology/server (build/certs bằng UID thường):

```bash
make build
make test-network
test -r certs/server.crt && test -r certs/server.key || make certs
set -o pipefail
sudo bash tests/system/run.sh --gate G08 2>&1 | tee docs/evidence/p8/g08-system.log
g08_status=${PIPESTATUS[0]}; printf 'g08_exit=%s\n' "$g08_status" | tee -a docs/evidence/p8/g08-system.log
```

Runner giữ network/probes/raw/CSV và gate-summary tại `results/p8-g08-96nOtS/`; actual rerun exit0/cleanup0 đã PASS RTT/counters/rate/loss, profile switch, tc-error và SIGINT cleanup. Agent đối chiếu tám successful trials/48 hashes và host snapshots, review ở [evidence P8](docs/evidence/p8/README.md). P8 đã PASS; người dùng đã cho phép riêng P9 theo runbook bên dưới.

## P9: runner, thống kê và G09

Chuẩn bị bằng user thường, từ repo root; dependencies đã được pin toàn bộ trong analysis/requirements.txt (Python3.14.4 / Matplotlib3.10.8 đã kiểm). Cài vào .tools/analysis, không cần venv/sudo pip:

```bash
make build
make analysis-deps
make test-analysis
test -r certs/server.crt && test -r certs/server.key || make certs
# Main benchmark: topology/server ban đầu absent, tự setup/probe/start/stop/cleanup.
make benchmark
# Dùng results_dir wrapper in ra:
make analyze RESULTS=results/<experiment-id>
```

Bench main dùng config defaults: 4 scenarios × 2 transports × (30 measured +2 warmups) =256 rows, 1536 resource rows. Schedule immutable, balanced AB/BA; fresh cold connection mỗi trial, qdisc reset/actual inspect trước và sau, seed khác mỗi pair. Performance traces tắt. Output gồm manifest/schedule/config/entries/shards/raw/runs.csv/streams.csv/network/probes/journals/merge.json, summary/resource-summary và PNG/SVG plots. Warmups không vào summary; failure rate luôn đi cùng latency, không bỏ outliers. Dataset nhỏ/WSL2/kernel-userspace/CC khác nhau nên kết luận chỉ cho testbed/workload này; plots không chứng minh HOL.

Lưu ý `make benchmark RUNS=... WARMUPS=... SEED=...` là override exploratory khi counts khác defaults; default đọc configs, không hardcode số thứ hai. `NETEM_SEED=none` chỉ chọn khi chủ động chấp nhận limitation seed=null. G09 đầy đủ kiểm actual interrupt/missing shard và main cohort:

```bash
set -o pipefail
sudo bash tests/system/run.sh --gate G09 2>&1 | tee docs/evidence/p9/g09-system.log
g09_status=${PIPESTATUS[0]}; printf 'g09_exit=%s\n' "$g09_status" | tee -a docs/evidence/p9/g09-system.log
```

Lượt G09 của agent trước đây bị sudo xác thực tương tác chặn; người dùng sau đó chạy actual gate và xác nhận P9/G09 PASS. Historical gate_root chứa main/ và interrupt/ cùng checker hashes/cleanup. Software evidence chỉ localhost correctness; xem [P9 runbook](docs/evidence/p9/README.md) để review files/failure policy và tái lập.

## P10: resumption, 0-RTT và G10

Cold target có TLS config/cache mới, không dùng ticket cũ. Mỗi resumed/early target tạo một cold connection riêng để nhận ticket qua `ClientSessionCache.Put` có state khác nil; đợi notification với deadline cấu hình, sau đó đóng prior connection. Ticket warm-up có t0 riêng, lưu tại `ticket-warmup/`; target bắt đầu t0 mới trên cùng server process. Resumed dùng Dial và đợi handshake; early dùng DialEarly, bắt đầu observer rồi enqueue REQUEST trước khi đợi handshake. Server dùng ListenEarly; `--allow-0rtt=false` cho phép từ chối early nhưng vẫn xử lý 1-RTT.

Một coordinator xử lý `Err0RTTRejected`: đợi tất cả workers cũ dừng, gọi NextConnection trên connection hiện tại, rồi replay toàn batch read-only tối đa một lần. Fallback giữ t0 target ban đầu, final resource rows thuộc attempt1; `attempts/<run_id>.json` giữ cả attempt0/1. Bytes final không cộng bytes đã bỏ. `tls_resumed`, `used_0rtt`, `early_rejected` lấy từ quan sát thực; state chưa xác định để null. Transfer thành công vẫn cần đủ bytes/FIN/hash. Successful fallback giữ `success=true`, đồng thời `used_0rtt=false`, `early_rejected=true`, `fallback_count=1`.

Kiểm ba mode trên localhost, hai terminal từ repo root:

```bash
# Terminal 1: giữ nguyên process giữa prior connection và target
bin/server --transport=quic --profile=handshake --listen=127.0.0.1:14436 --allow-0rtt=true
# Terminal 2: mỗi lệnh tự lưu target, prior ticket warm-up và attempts
bin/client --transport=quic --profile=handshake --mode=cold --addr=127.0.0.1:14436 --server-name=localhost
bin/client --transport=quic --profile=handshake --mode=resumed --addr=127.0.0.1:14436 --server-name=localhost
bin/client --transport=quic --profile=handshake --mode=early --addr=127.0.0.1:14436 --server-name=localhost
```

`make benchmark-handshake` dùng 1×1024 bytes, rtt50-loss0, ba QUIC modes × (30 measured +2 target warmups) =96 target rows. Có thêm 64 ticket warm-ups riêng cho resumed/early, không vào CSV aggregate hoặc denominator target. Schedule cân bằng sáu permutations: mỗi mode ở mỗi vị trí 10 lần trong 30 measured triples; seed chung một triple, đổi giữa triples, qdisc reset trước từng invocation. Bulk P9 giữ riêng. Summary/plots tách cold/resumed/early và báo `n_success`, `n_failed`, `n_mode_achieved`, `n_fallback`, `n_unachieved`; fallback hoặc mode chưa đạt không vào latency distribution của mode dự định.

Chuẩn bị build/deps/certs bằng UID thường, dừng server/topology cũ, rồi chạy trong Ubuntu WSL2:

```bash
make build
make test-analysis
test -r certs/server.crt && test -r certs/server.key || make certs
# Full G10: functional/rejection/error cases, default ingress IFB cohort và cleanup
set -o pipefail
sudo bash tests/system/run.sh --gate G10 2>&1 | tee docs/evidence/p10/g10-user-run.log
g10_status=${PIPESTATUS[0]}
printf 'g10_exit=%s\n' "$g10_status" | tee -a docs/evidence/p10/g10-user-run.log
```

G10 actual đang BLOCKED ở sudo authentication, chưa có dataset impairment P10. Localhost API qualification yêu cầu actual TLS resumption/Used0RTT, không rejection/fallback, và `request_end_ms < handshake_ms` của target. Handshake là lúc client observer nhìn thấy hoàn tất, có scheduling delay; Write return chỉ chứng minh API đã nhận REQUEST. Packet 0-RTT chứa application request, qlog/PCAP/progress và full corroboration thuộc P11, chưa thực hiện. Review ticket lifecycle/deadlines, observer, coordinator một replay, valid-ticket rejection harness, final-attempt CSV/state và failure denominators tại [P10 evidence](docs/evidence/p10/README.md).

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

Hiện có targets build/test/test-race/certs/doctor và P7/P8 setup-network/server/netem/inspect-network/clear-netem/clean-network/test-network. P9 có benchmark/analyze/analysis-deps/test-analysis; P10 thêm benchmark-handshake. Demo/capture và đóng gói/rehearsal thuộc P11/P12.

## P11 evidence

`make decoder-deps` chuẩn bị decoder tshark4.6.4 cục bộ từ packages/hash pinned, không cài hệ thống. `make gate-g11` build bằng user rồi chạy full gate qua sudo. Lệnh có tee/exit capture, trạng thái subcases và review tại [runbook P11](docs/evidence/p11/README.md). Traces không được gộp vào main performance; TLS keylogs giữ local mode0600.
