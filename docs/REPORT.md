# Báo cáo thực nghiệm — QUIC Performance Lab / T03

Cập nhật 2026-10-03 (Asia/Saigon). Lab đã triển khai raw QUIC và TCP/TLS multiplex, đo bulk/handshake trên ingress IFB thật và thu bằng chứng UDP, accepted 0-RTT, ordering HOL. **G00–G12 PASS; actual G12 g12_exit0/fullcheckerPASS và live360.000794s**; xem [ACCEPTANCE_RESULTS](ACCEPTANCE_RESULTS.md) và [hồ sơ P12](evidence/p12/README.md). Báo cáo phục vụ review; không xác nhận nhóm đã bảo vệ hoặc nộp slides.

## 1. Phạm vi đã triển khai

Server có TCP và UDP listener cùng port 4433, certificate/TLS 1.3/ALPN `quicbench/1` dùng chung, resource store immutable trong RAM. TCP dùng **một connection**, QB01 header 24 bytes và một writer round-robin theo chunk 16 KiB cho sáu logical resources. QUIC dùng **một connection**, một client-initiated bidirectional stream/resource với native stream ID được ghi thực; response workers ghi độc lập sau shared batch barrier. Server/client/bench chạy UID thường; wrapper đặc quyền quản namespace/qdisc/capture/entry và cleanup theo ownership.

Các phần đã có: bounded framing/workload, partial I/O/cancellation; monotonic metrics và hash sau transfer; canonical JSON/CSV kể cả failures; ingress IFB/mirred và metadata trước/sau; immutable schedule/merge/statistics/plots; ticket notification và một replay khi early bị từ chối; qlog/progress/paired PCAP/decoder/viewer. [Acceptance G00–G11](ACCEPTANCE_RESULTS.md). HTTP/3, GUI application, migration demo, multi-TCP và custom QUIC cryptography thuộc ngoài mandatory scope.

## 2. Môi trường và phương pháp

| Thành phần | Quan sát/cấu hình thực |
|---|---|
| Execution | Ubuntu 26.04.1 LTS dưới WSL2; Windows 11 do user báo, chưa truy vấn Windows CLI trong manifests |
| Kernel/tài nguyên | `6.18.40.1-microsoft-standard-WSL2`, x86_64; 2 logical CPUs; MemTotal 2981596 KiB, swap 2097152 KiB; chia sẻ host/kernel |
| Toolchain | Go 1.27.1, quic-go v0.63.0; Python 3.14.4, Matplotlib 3.10.8; [pins/receipts](VERSIONS.md) |
| TLS/QUIC | Actual sidecars ghi TLS 1.3, ALPN `quicbench/1`, QUIC v1; cipher/socket buffers theo từng `shards/<run_id>/connection.json` |
| Congestion control | Namespace kernel setting TCP=`cubic`, app không override per-socket CC; quic-go đúng tag dùng Reno; CC khác nhau |
| Topology | qclient 10.10.0.1 ↔ veth eth0 ↔ qserver 10.10.0.2; MTU 1500; receiver ifb0 mỗi namespace, ingress flower/mirred |
| Impairment | 20 Mbit/s mỗi chiều, limit 1000 packets; baseline d=0/loss0; RTT50 scenarios d=25 ms mỗi chiều/downstream loss0/1/3%, upstream0% |
| Offload/seeds | Inspect/tắt segmentation/coalescing features khi mutable; snapshots giữ fixed/absent; same pair seed không đồng nghĩa cùng lost bytes |

Mỗi bulk trial truyền 6×1048576 bytes=6291456 bytes, chunk 16384, byte(i,j)=`(i+j)%256`, checksum SHA-256. Data/buffers/cert chuẩn bị trước t0; không đo SSD. Main cold suite có 4 scenarios×2 transports×30 measured=240, cộng 16 warmups riêng. Sequential AB/BA balanced, reset netem trước mỗi transport sau probes/server idle. Handshake suite dùng 1×1024 bytes/chunk1024, rtt50-loss0, 30 measured/cold,resumed,early và 2 target warmups/mode; 64 prior ticket connections được lưu ngoài 96 target rows. Cold cache rỗng; resumed/early chờ actual ticket signal trong cùng client process/server process.

Probes 12 mẫu/mỗi chiều: P9 baseline median 0.3725/0.2685 ms, rtt50-loss0 median 50.85/50.55 ms; P10 baseline 0.2635/0.281 ms và rtt50-loss0 50.4/50.4 ms. Các số trong tolerance; không ping nền trong transfer, không gọi qdisc drops là empirical random-loss rate. [P9 probe](../results/p9-g09-8dFdkj/main/probes/baseline-qclient.log.json), [P10 probe](../results/p10-g10-cR1oR9/main/probes/rtt50-loss0-qclient.log.json).

Durations lấy `time.Time.Sub` trong cùng client process. `ttfa_ms` là DATA payload byte đầu toàn trial từ t0; `total_ms` kết thúc ở FIN cuối; `goodput_mbps`=8×payload/(transfer_ms×1000), không gồm headers/retransmissions. Warmups loại khỏi measured statistics; scheduled failures giữ denominator. Mean/median, nearest-rank p95=`ceil(.95n)-1`, sample SD mẫu n−1; không xóa outliers hoặc pooling sáu correlated resources thành sáu independent trials. [Hợp đồng metrics](METRICS_AND_RESULTS.md).

## 3. Datasets và provenance

| Dataset thật | Experiment/run mapping | Denominator/kết quả | Nguồn |
|---|---|---|---|
| P9 bulk performance | `bulk_20261001T064654_138b43853c623b9e`, root `p9-g09-8dFdkj/main` | 256 scheduled/invoked/success, 0 failed/missing; 240 measured+16 warmups; 1536 resource rows | [manifest](../results/p9-g09-8dFdkj/main/manifest.json), [runs](../results/p9-g09-8dFdkj/main/runs.csv), [streams](../results/p9-g09-8dFdkj/main/streams.csv), [audit/archive](evidence/p9/README.md) |
| P10 handshake performance | `bulk_20261002T024416_374361bd2627ff92`, root `p10-g10-cR1oR9/main` | 96 successful targets, 0 failed; 90 measured+6 warmups; 64 prior warmups riêng; 30 achieved/mode measured, 0 fallback/unachieved | [manifest](../results/p10-g10-cR1oR9/main/manifest.json), [runs](../results/p10-g10-cR1oR9/main/runs.csv), [summary](../results/p10-g10-cR1oR9/main/summary.csv), [audit/archive](evidence/p10/README.md) |
| P11 instrumented evidence | `p11-g11-6a8cc99602b7`: `handshake_cold/resumed/early`, `loss_0..9_tcp/quic` | 23 planned/invoked/success, 0 failed; all 10 HOL pairs retained; first qualifying pair0 selected | [manifest](../results/p11-g11-6a8cc99602b7/manifest.json), [checker](../results/p11-g11-6a8cc99602b7/g11-check.json), [notes](../results/p11-g11-6a8cc99602b7/evidence-notes.md), [P11 evidence](evidence/p11/README.md) |

P9/P10 instrumentation nặng tắt; P11 instrumented timings không gộp performance. Manifests/build/source/config hashes là provenance của **binary đã chạy**, không thay bằng source tree hiện tại. P9/P10 generated `report.md` còn câu “P11 pending” theo thời điểm tạo; giữ historical artifacts, closure P11 ở checker/ledger hiện hành. Local software datasets chỉ correctness. Historical failed G07/G08/G11 runs và sudo-blocked attempts giữ nguyên, không thay thành successful benchmark rows.

## 4. Bulk kết quả đo

Mỗi hàng dưới có attempted30/success30/failed0, failure rate0%, n_values30; latency **ms**, goodput **Mbps**. Làm tròn 3 decimals từ [summary.csv](../results/p9-g09-8dFdkj/main/summary.csv); đầy đủ e2e-goodput/handshake và từng resource tại [resource-summary.csv](../results/p9-g09-8dFdkj/main/resource-summary.csv). [Plots có n/failures/units](../results/p9-g09-8dFdkj/main/plots/index.json).

| Scenario | Transport | Metric | Mean | Median | p95 | Sample SD |
|---|---|---|---:|---:|---:|---:|
| baseline | QUIC | total_ms | 2660.264 | 2654.793 | 2728.348 | 19.416 |
| baseline | TCP | total_ms | 2651.065 | 2649.439 | 2660.067 | 4.865 |
| rtt50-loss0 | QUIC | total_ms | 2813.697 | 2811.900 | 2824.929 | 5.685 |
| rtt50-loss0 | TCP | total_ms | 2971.508 | 2970.568 | 2979.177 | 3.871 |
| rtt50-loss1 | QUIC | total_ms | 12526.162 | 12354.308 | 15358.483 | 1858.512 |
| rtt50-loss1 | TCP | total_ms | 18552.591 | 18312.296 | 22729.866 | 2950.179 |
| rtt50-loss3 | QUIC | total_ms | 24691.710 | 24762.367 | 26574.108 | 1215.438 |
| rtt50-loss3 | TCP | total_ms | 41124.962 | 40898.681 | 45210.192 | 2474.297 |
| baseline | QUIC | ttfa_ms | 11.629 | 8.547 | 26.727 | 14.559 |
| baseline | TCP | ttfa_ms | 15.540 | 14.125 | 24.994 | 4.792 |
| rtt50-loss0 | QUIC | ttfa_ms | 110.756 | 109.297 | 119.531 | 5.082 |
| rtt50-loss0 | TCP | ttfa_ms | 266.440 | 265.171 | 274.205 | 3.838 |
| rtt50-loss1 | QUIC | ttfa_ms | 120.312 | 111.109 | 136.968 | 40.556 |
| rtt50-loss1 | TCP | ttfa_ms | 349.195 | 268.502 | 1271.995 | 263.785 |
| rtt50-loss3 | QUIC | ttfa_ms | 124.993 | 111.983 | 181.390 | 35.805 |
| rtt50-loss3 | TCP | ttfa_ms | 313.319 | 306.345 | 400.821 | 71.662 |
| baseline | QUIC | goodput_mbps | 18.988 | 19.004 | 19.009 | 0.092 |
| baseline | TCP | goodput_mbps | 19.033 | 19.037 | 19.039 | 0.013 |
| rtt50-loss0 | QUIC | goodput_mbps | 18.264 | 18.269 | 18.281 | 0.018 |
| rtt50-loss0 | TCP | goodput_mbps | 17.566 | 17.570 | 17.580 | 0.017 |
| rtt50-loss1 | QUIC | goodput_mbps | 4.133 | 4.094 | 5.313 | 0.662 |
| rtt50-loss1 | TCP | goodput_mbps | 2.809 | 2.765 | 3.601 | 0.466 |
| rtt50-loss3 | QUIC | goodput_mbps | 2.049 | 2.037 | 2.245 | 0.102 |
| rtt50-loss3 | TCP | goodput_mbps | 1.232 | 1.234 | 1.373 | 0.076 |

Trong workload/testbed này, baseline total median gần nhau: TCP 2.649 s, QUIC 2.655 s. RTT50/loss1%: median TCP 18.312 s, QUIC 12.354 s; loss3%: 40.899 s và 24.762 s. Đây là quan sát tổng hợp implementations cụ thể; completion table không tách riêng HOL khỏi CC/scheduling/TLS/packetization.

## 5. Cold/resumed/early

Mỗi mode có 30 attempted/transfer success/mode achieved, 0 failed/fallback/unachieved, n_values30; đơn vị **ms**. [Summary](../results/p10-g10-cR1oR9/main/summary.csv), [plots](../results/p10-g10-cR1oR9/main/plots/index.json).

| Mode | Metric | Mean | Median | p95 | Sample SD |
|---|---|---:|---:|---:|---:|
| cold | handshake_ms | 56.862 | 55.792 | 61.359 | 2.155 |
| resumed | handshake_ms | 57.348 | 55.228 | 68.162 | 7.204 |
| early | handshake_ms | 56.175 | 55.051 | 60.952 | 2.426 |
| cold | ttfa_ms | 110.100 | 108.090 | 118.208 | 5.003 |
| resumed | ttfa_ms | 110.606 | 108.743 | 121.441 | 7.993 |
| early | ttfa_ms | 56.306 | 55.164 | 60.996 | 2.645 |
| cold | total_ms | 110.106 | 108.099 | 118.212 | 5.003 |
| resumed | total_ms | 110.614 | 108.765 | 121.445 | 7.992 |
| early | total_ms | 56.313 | 55.168 | 61.002 | 2.646 |

Early TTFA median 55.164 ms so resumed 108.743 ms: early REQUEST giảm khoảng một RTT chờ trong trao đổi 1 KiB này; handshake completion vẫn khoảng 55 ms, không phải response trong 0 ms. P10 đánh giá mode bằng actual DidResume/Used0RTT và REQUEST API enqueue trước observed handshake; observer có scheduling delay. P11 bổ sung **một sample evidence riêng**, không giải mã từng performance trial: `handshake_early`, target ODCID `fa0b840a130507ee427c668e7c1de24598e4`, UDP34352→4433, decrypted frame14/0-RTT PN0/native stream0/offset0/length32 chứa đúng QB01 REQUEST(resource1,batch1,size1024); client-sent/server-received qlog cùng PN/stream/range và actual state corroborate. Cùng witness tại hai capture points không phải hai independent requests. [Early proof](../results/p11-g11-6a8cc99602b7/early-packet-check.json), [viewer](../results/p11-g11-6a8cc99602b7/viewers/handshake_early.html), [PNG](../results/p11-g11-6a8cc99602b7/viewers/handshake_early.png).

Forced-rejection functional test giữ valid ticket keys, đổi Allow0RTT, actual DidResume=true/Used0RTT=false; sáu workers join, coordinator `NextConnection`, replay đúng một lần với t0 gốc, 6144 final bytes/hashes và attempts history. Đây là correctness harness riêng, không observed failure rate của performance cohort. [G10 rejection evidence](evidence/p10/README.md). Read-only workload không xóa replay risk; [RFC9001§9.2](https://www.rfc-editor.org/rfc/rfc9001.html#section-9.2).

## 6. UDP và HOL bằng trace

G11 qlog/UDP decode/progress/early/HOL đều PASS; original_exit=cleanup_exit=0, host link/address/route before/active/final byte-equal. 23 attempts gồm 3 handshake và 10 bulk pairs; cả 20 bulk HOL candidates PASS. Checker chọn **pair qualifying đầu tiên**, `loss_0_tcp`/`loss_0_quic`, seed2026100201, rtt50-loss3; không chọn pair QUIC thắng nhiều nhất. [Full checker/selection](../results/p11-g11-6a8cc99602b7/g11-check.json).

| Witness | Sự kiện quan sát | Giới hạn diễn giải |
|---|---|---|
| TCP `loss_0_tcp` | Gap raw sequence3187438027; SACK[3187439475,3187440923), ACK frame237 chưa tiến qua gap; original228, later-byte229, retry248; ACK tiến ở253. Cửa sổ app stall được checker chấp nhận ≈46.764 ms. | ACK/SACK corroborate receipt sau gap/recovery; progress resolution16KiB, trim3ms mỗi cạnh. TLS encrypted bytes không định danh resource mất. |
| QUIC `loss_0_quic` | Server loss PN25: stream20/resource6 range[1345,2602); client nhận later offset2602 ở PN30; resource5 đạt16384 payload bytes trong cửa sổ gap checker≈42.902ms; recovery ở **PN50 mới**, affected stream tiếp tục. | Client receive qlog+payload progress hỗ trợ sibling ordering independence; packet có thể mang nhiều streams và flow/congestion vẫn shared. |

Mở [TCP viewer](../results/p11-g11-6a8cc99602b7/viewers/loss_0_tcp.html), [QUIC viewer](../results/p11-g11-6a8cc99602b7/viewers/loss_0_quic.html), hoặc [TCP PNG](../results/p11-g11-6a8cc99602b7/viewers/loss_0_tcp.png)/[QUIC PNG](../results/p11-g11-6a8cc99602b7/viewers/loss_0_quic.png). PCAP tại `captures/<run_id>/{qclient,qserver}/capture.pcap`, derived packets/PDML trong `decoded/`; correlated qlog tại `traces/<run_id>/`, progress tại `runs/<run_id>/progress.csv`. Eth0 AF_PACKET có thể thấy packet trước IFB drop; không dùng receiver capture đơn độc chứng minh app đã nhận. Same-host wall alignment chỉ hỗ trợ correlation với 3 ms margin; latency vẫn dùng client monotonic clock.

Trace là một ordering-mechanism witness trên lab; không đo tỉ lệ performance gain do riêng HOL, không khẳng định mọi loss chỉ ảnh hưởng một stream, không loại ordered delivery trong cùng stream. [RFC9000§2](https://www.rfc-editor.org/rfc/rfc9000.html#section-2), [§13.3](https://www.rfc-editor.org/rfc/rfc9000.html#section-13.3), [RFC9002§6](https://www.rfc-editor.org/rfc/rfc9002.html#section-6).

## 7. Tái lập, kiểm định và giới hạn

Ubuntu WSL2/native Linux filesystem; setup/dependencies/build/cert trước live theo [README](../README.md). Network sudo là privilege gate thật. Chạy từng lệnh riêng; wrappers tạo output root mới, cleanup tài nguyên thuộc lab:

```bash
make doctor
make build
make test
make test-race
make benchmark
make benchmark-handshake
bash scripts/run-g11-review.sh
make demo-quic-basic
make demo-loss
make demo-0rtt
make clean-network
```

Tái sinh derived analysis từ CSV đã lưu hoặc kiểm cohort (checker ghi lại derived check file; không sửa raw):

```bash
make analyze RESULTS=results/p9-g09-8dFdkj/main
make analyze RESULTS=results/p10-g10-cR1oR9/main
python3 tests/system/check_g09.py results/p9-g09-8dFdkj/main
python3 tests/system/check_g10.py results/p10-g10-cR1oR9/main
```

Actual G11 checker đã sinh notes/viewers/decode tại root nêu trên. Keylogs local0600 không có trong public archive; giải mã lại cần local secrets hoặc capture mới theo runner. G12 exact command/checker/fresh reproduction/rehearsal status ở [P12 runbook](evidence/p12/README.md); [DEMO_SCRIPT](DEMO_SCRIPT.md) là kịch bản5–7 phút/fallback. G12 actual PASS bổ sung fresh reproduction/Make demos/live360.000794s/cleanup vào G00–G11 đã PASS; localhost không thay end-to-end network PASS.

Giới hạn: cùng WSL2 host/kernel/CPU và có swap, không CPU isolation; TCP kernel CUBIC so quic-go userspace Reno khác CC/scheduler/packetization/offload; server per-socket buffers chưa sampled; Windows/WSL version chưa queried ở manifests; queue/drop có thể gồm overflow; 30 samples/p95 chỉ mô tả testbed này; impairment tác động control/ACK/handshake theo hướng. Interactive terminal Ctrl+C qua tee ở historical P9 từng exit141/cleanup1; controlled interrupt130/cleanup0 và P11 fixes không xác minh mọi terminal path. First-load IFB sau fresh boot chưa kiểm lại. Không extrapolate Internet, không tuyên bố QUIC luôn nhanh hơn TCP hoặc UDP tự tạo tốc độ.

P11 build dùng **build-only Go crypto/tls early-keylog overlay** D28: generator kiểm exact Go/source hashes, thêm hai optional secret-export calls; không thay GOROOT/module cache/crypto algorithms/pins. `make build/test/test-race` áp cùng overlay/receipts; standalone `go build` không tái lập binary evidence. P9/P10 historical binaries trước overlay giữ provenance riêng. [Versions](VERSIONS.md), [AI_USAGE](AI_USAGE.md), [sources](REFERENCES.md), [traceability](TRACEABILITY.md). Human review/code understanding/slides submission còn do nhóm thực hiện; không suy từ test PASS.

## 9. P12 reproduction và actual G12 closure

Fresh local detached checkout base`8721f6346bf62cdab9aa653c9105e1ad3ed9516e` + exact candidate594 source hashes tại `results/p12-g12-18124ccd073d`:14 steps exit0, source/pins/build/cert/doctor/full Go+Python checks,12demo+19G12 negatives, actual localhost5success+1expected TLS failure, archived actual G09 `make analyze` với1028 canonical hashes unchanged. Dependency caches được chuẩn bị offline; không kế thừa app/cert/results/build cache và không tạo user commit. [Receipt](evidence/p12/g12-source-software.json), [package check](evidence/p12/g12-packaging-check.json), [public archive/review](evidence/p12/README.md).

Checkpoint lịch sử: agent sudo attempt exit1 trước runner, interactive authentication required. User đã chạy actual G12 results/p12-g12-7807db3f7c56: software14/14 và bốn demo/cleanup exit0; rehearsal423.01996559s>420s **FAIL**, final checker NOT_RUN. D31 tách mandatory baseline acceptance trước clock theo live A→C→B, giữ full proof/cleanup và300–420s. Tại checkpoint lịch sử đó patched full rerun cần NEW actual run và agent sudo authentication blocked; current fullPASS closure bên dưới supersedes. [Independent as-run audit](evidence/p12/g12-user-fail-review.json). First software packaging FAIL vì status-cell `PASS actual` còn lưu, không sửa raw; final normalized-cell fresh run PASS. Nhóm chạy `bash scripts/run-g12-review.sh` trong terminal Ubuntu rồi review actual receipts/lifecycle/proofs/report/ownership; không coi software success là full gate.

D31 historical patched software checkpoint (superseded by closure below): results/p12-g12-timing-20261002 fresh605files,14/14steps PASS,12demo+24G12 regressions,localhost5success+1expectedTLSfailure,1028canonicalhashes unchanged. Baseline mandatory preparation trước live A→C→B; tại checkpoint này actual new preparation/rehearsal NOT_RUN vì sudo exit1 before runner; current fullPASS bên dưới supersedes. [Current review](evidence/p12/g12-review.json); đây không là số liệu performance hoặc live duration mới.

Closure actual P12/G12 — 2026-10-03 (Asia/Saigon): user `bash scripts/run-g12-review.sh` tại results/p12-g12-51c13b94f99b `g12_exit=0`,fullcheckerPASS.14softwaresteps/610sourcehashes,8/8demo successes,live360.000793725s (300–420s),baseline preparation177.218538684s riêng trước live. Actualearly/HOL/probes/IFB/UID/cleanup0/hostunchanged PASS;independent read-only [closure audit](evidence/p12/g12-rerun-review.json), [public bundle](evidence/p12/g12-user-run-artifacts.tar.gz). Earlier423sFAIL/sudoBLOCKED retained;no raw/receipt/source rewrite, implementation unchanged. Dừng human review/codeownership/oraldelivery/slides;no commit/upload/nextphase.
