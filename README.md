# QUIC Performance Lab

PTIT Lập trình mạng T03: TCP/TLS multiplex trên **một connection** và raw QUIC trên UDP, cùng payload trong RAM và certificate. Chạy trong Ubuntu WSL2 trên Windows 11, repository trong `/home/...`; mở Windows VS Code bằng Remote WSL. Đây là lab CLI, không phải website HTTP/3.

**P0–P12/G00–G12 PASS (2026-10-03, Asia/Saigon).** Actual G12 `results/p12-g12-51c13b94f99b`, `g12_exit=0`:610 source files,14/14software steps,8/8successful demo trials,live360.000794s/cleanup0,early REQUEST và live causal HOL PASS. Baseline preparation177.218539s riêng trước live. [G12 closure audit](docs/evidence/p12/g12-rerun-review.json). Human code/oral/slides review còn do nhóm thực hiện. Actual G11: `results/p11-g11-6a8cc99602b7`,23/23 success, paired packet0RTT REQUEST và HOL causal witnesses PASS, cleanup0/host unchanged. [Ledger](docs/ACCEPTANCE_RESULTS.md), [P11 audit](docs/evidence/p11/g11-rerun-review.json), [P12 gate/evidence](docs/evidence/p12/README.md), [TASK](.codex/TASK.md). Các lượt FAIL/BLOCKED lịch sử vẫn được giữ. Chỉ P12 được authorize, sau gate dừng human review; không tự commit hoặc nộp bài.

## Chuẩn bị một lần, trong Ubuntu WSL2

Cần Bash/Make/curl/tar/SHA256/OpenSSL/Python3+pip/GCC, iproute2/iputils-ping/ethtool/tcpdump/kmod/util-linux/ripgrep. Kiểm phiên bản/môi trường trong [VERSIONS](docs/VERSIONS.md); `make doctor` chỉ inventory, không thay network gate. Dependency bootstrap cần mạng; live demo và G12 dùng dependency đã chuẩn bị offline. Việc cài mới hệ điều hành chưa được kiểm bằng G12.

Từ root repository sau checkout/candidate source overlay, cài exact toolchain (không dùng `@latest`):

```bash
curl -fL https://go.dev/dl/go1.27.1.linux-amd64.tar.gz -o /tmp/quic-lab-go1.27.1.tar.gz
echo '63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445  /tmp/quic-lab-go1.27.1.tar.gz' | sha256sum -c -
mkdir -p .tools/go1.27.1
tar -xzf /tmp/quic-lab-go1.27.1.tar.gz -C .tools/go1.27.1 --strip-components=1
export PATH="$PWD/.tools/go1.27.1/bin:$PATH"
export GOTOOLCHAIN=local GOPATH="$PWD/.tools/gopath" GOCACHE="$PWD/.tools/gocache"
go mod download
go mod verify
make analysis-deps
make decoder-deps
make build
make certs
make doctor
make test
make test-race
make test-analysis
make test-network
make test-demo
```

Nếu `.tools/go1.27.1` đã có đúng version/hash thì dùng lại. `make certs` tạo identity demo30 ngày/SAN localhost,127.0.0.1,10.10.0.2, key0600; từ chối overwrite. Chỉ thay identity khi chủ động dừng mọi server: `make certs CERT_FORCE=--force`. `.tools/`, binaries, results và secrets gitignored.

Build/test dùng hash-checked Go1.27.1 **build-only TLS early-keylog overlay** D28; không sửa installed GOROOT/module cache, không thêm crypto. `bin/build.json` bind source/binary/overlay hashes. Không build thủ công thiếu overlay hoặc dùng binary cũ sau đổi source/Make. quic-go v0.63.0, QUIC v1/TLS1.3/ALPN `quicbench/1` đã pin.

## Kiểm correctness nhanh

Sau build/certs, terminal1:

```bash
mkdir -p results
bin/server --transport=both --profile=bulk --listen=127.0.0.1:4433 --ready-file=results/local-ready
```

Terminal2:

```bash
bin/client --transport=tcp --mode=cold --profile=bulk --addr=127.0.0.1:4433 --server-name=localhost --format=table
bin/client --transport=quic --mode=cold --profile=bulk --addr=127.0.0.1:4433 --server-name=localhost --format=table
```

Mỗi client ghi thư mục mới và canonical raw/CSV;6 resources×1MiB, hash chỉ kiểm sau timing. Dừng server bằng Ctrl+C. Localhost chỉ xác nhận correctness, không phải performance/impairment evidence.

## Demo offline, một lệnh mỗi phần

Dừng foreground server/benchmark cũ trước khi chạy. Dependency/binary/cert đã chuẩn bị; các target sau không build/download. Mỗi wrapper tạo hoặc dùng lại **owned idle topology**, tự quản server đúng profile/readiness/capture, chạy app UID thường rồi clear/teardown; không kill process không rõ chủ. Không cần setup thủ công.

```bash
make demo-quic-basic
make demo-baseline
make demo-loss
make demo-0rtt
make cleanup
```

`demo-quic-basic`: QUIC/handshake baseline + paired UDP PCAP/qlog. `demo-baseline`: TCP+QUIC bulk no-loss. `demo-loss`: một pair bulk rtt50-loss3, giữ trace/status thật. `demo-0rtt`: cold/resumed/early1KiB; prior tickets riêng và actual state+decoded REQUEST. Results path được in; xem `demo-check.json`, `demo.json`, `runs/`, `viewers/`, `captures/`, `traces/`, `network/`, `cleanup.json`.

Có thể đặt `DEMO_OUT` thành absolute **new directory** có parent sẵn và `DEMO_BACKUP` trỏ tới original accepted G11 root. `NETEM_SEED=none` là explicit limitation; mặc định dùng seed. Một sample loss có thể INCONCLUSIVE; chỉ dùng backup đã verify và nói rõ pre-recorded. Không rerun đến khi QUIC thắng. [Kịch bản5–7 phút](docs/DEMO_SCRIPT.md).

## Benchmark và analysis

```bash
make benchmark
make benchmark-handshake
```

Main ingress-ifb giữ4 scenarios×2 transports×(30 measured+2 warmups)=256 runs/1536 resources, cold cache và instrumentation OFF. Handshake96 targets=90 measured+6 warmups,64 prior-ticket connections ngoài denominator. Wrapper in experiment path. Dùng `make analyze RESULTS=...` với **path thật vừa in**; validate→summary→plots/report, không sửa raw. `RUNS/WARMUPS/SEED` overrides thay cohort mặc định là exploratory. Lỗi infra dừng cohort; failures luôn giữ trong mẫu số. Không chạy full suite trong5–7 phút live.

Dữ liệu được audit: [P9](docs/evidence/p9/README.md), [P10](docs/evidence/p10/README.md). Report tổng hợp, denominators/median/p95/stddev và giới hạn ở [REPORT](docs/REPORT.md). Public archives giữ raw/canonical/provenance và assets thật; P11 PCAP/keylog/bulky PDML giữ local, không upload secrets mặc định.

## Full G12 và kiểm lại các gate

```bash
bash scripts/run-g12-review.sh
```

Cũng có `make gate-g12`. G12 tạo fresh local Git checkout của HEAD rồi overlay current candidate source vào directory mới, không kế thừa bin/certs/results hay Go build cache; dependency đã pin dùng cache offline được công khai. Fresh checkout có own `.git`/base commit, không kế thừa parent VCS; đây là **fresh local checkout với exact candidate overlay/hashes**, chưa claim một remote commit mới đã checkout. Gate build/certs/tests/localhost+TLS failure/analyze archived real cohort rồi sudo chạy baseline acceptance trước đồng hồ live, basic→loss→0rtt→cleanup trong timed offline walkthrough5–7 phút, cuối cùng independent proof/cleanup checker cho **cả bốn Make demos**. Preparation receipt riêng và SHA/chronology được bind vào live; không nới300–420s (D31). Human spoken rehearsal/ownership review vẫn thuộc nhóm; không tự nhận đã nộp slides.

Nếu sudo cần password, nhập trong terminal Ubuntu của bạn; không gửi password trong chat. Gate có log/exit/path thật. Agent bị quyền chặn phải ghi G12 BLOCKED, không thay bằng software PASS. [Exact reproduction và trạng thái subcases](docs/evidence/p12/README.md).

Khi cần tái lập riêng gate cũ, chuẩn bị build/deps/cert bằng UID thường rồi `sudo bash tests/system/run.sh --gate G08` (tương tự G09/G10/G11); không flag là G07. P11 ordinary-user entry: `bash scripts/run-g11-review.sh`. Không cần rerun các gate đã PASS chỉ để chạy P12.

## Cleanup và lỗi thường gặp

- Existing namespace/server: dừng foreground server bằng Ctrl+C; `make clean-network` chỉ xóa owned namespace không còn PID. Demo từ chối active/foreign topology; không xóa mù.
- `make cleanup` là alias teardown an toàn, giữ mọi result. Wrapper tự dừng đúng processes của nó. Nếu bị SIGKILL không thể trap, xem named namespace/PID/receipt rồi xử lý thủ công đúng ownership.
- Build receipt stale: `make build` bằng user trước trial mới; không sửa receipt lịch sử.
- IFB/seed/tool/permission không đạt: giữ log và nonzero, không downgrade main sang egress-demo.
- Cert/key/qlog/keylog là local evidence; keylogs0600 cần để giải mã Wireshark/Tshark. `scripts/tshark.sh` dùng decoder pinned đã chuẩn bị. Viewer HTML/PNG/SVG đọc quic-12 JSON-SEQ, không đổi đuôi file để giả qvis compatibility.

Giới hạn: cùng WSL kernel/CPU, TCP kernel CUBIC và quic-go Reno/scheduling khác nhau, packetization và congestion shared; configured loss ảnh hưởng downstream control packets. Main completion charts không đủ chứng minh HOL; G11 có ACK/SACK gap và native stream/sibling-progress witnesses riêng. Windows11 là user-reported; WSL app version chưa truy vấn Windows CLI. Interactive terminal Ctrl+C qua tee G09 từng141/cleanup1 là lịch sử chưa được xác minh lại bằng đường controlled interrupt.

[Đặc tả](docs/DEMO_SPEC.md) · [Protocol](docs/PROTOCOL.md) · [Metrics](docs/METRICS_AND_RESULTS.md) · [Network](docs/NETWORK_AND_BENCHMARK.md) · [CLI](docs/CLI_CONTRACT.md) · [Traceability](docs/TRACEABILITY.md) · [AI disclosure](docs/AI_USAGE.md) · [Q&A và slide outline](docs/THEORY_AND_DEFENSE.md)
