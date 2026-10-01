# Truy vết toàn bộ nguồn và trao đổi

## 1. Phạm vi đọc

Ba attachments: INT1433 66 dòng, network-programing-topic 571 dòng, T03 1707 dòng. Mọi đầu mục phụ/các topic khác và thông tin hành chính vẫn có nguyên văn trong originals, không biến thành requirement lab.

Phần hội thoại chuyển vào bắt đầu giữa mục 1 và có cờ lược bỏ phần trước. Bảng 31 mục dưới đối chiếu **phần nhìn thấy**, không giả làm transcript nguyên văn. Personal context tìm lại nhóm3/phân công/tính cụ thể của demo; người dùng xác nhận không có thêm quyết định và chọn Ubuntu VM trong handoff gốc ngày 2026-09-28.

## 2. Đối chiếu 31 mục của thiết kế trao đổi

| Mục | Ý cần bảo toàn | Chỗ hiện thực hóa / nghiệm thu |
|---:|---|---|
| 1 | Client/server cùng workload; RTT/loss/rate; connect/TTFB/resource completion/total/throughput | SPEC; METRICS; G04/G05/G09 |
| 2 | CLI trước, terminal/Wireshark/qlog/qvis/CSV/chart; GUI optional; số output chỉ minh họa | SPEC§1, CLI, DEMO; không nhập số giả |
| 3 | VS Code/Go/quic-go/Linux; Windows có WSL2 hoặc Ubuntu VM; netem Linux-specific | CONTEXT D03: lựa chọn VM gốc; D13 (2026-09-30): WSL2 hiện hành sau capability preflight; NETWORK§1; G00 |
| 4 | Localhost không đại diện; namespaces như 2 endpoints nhẹ, không 2 VMs | NETWORK§2; G07 |
| 5 | qclient/qserver, veth move/rename, 10.10.0.1/.2, lo/eth0 up, ping | NETWORK§2; P7/G07 |
| 6 | tc ngoài Go; delay25 mỗi hướng → RTT≈50 | NETWORK§3–5; G08; không double shape |
| 7 | Downstream loss cho main; symmetric optional | NETWORK§4; C01 làm rõ không data-only |
| 8 | Project Go thật: cmd/internal/config/scripts/certs/results/docs/Makefile/modules | PLAN file map; scaffold dirs; P0–P12 |
| 9 | Một client transport flag, server hai listeners TCP/UDP cùng :4433 | CLI/SPEC§2; G04 |
| 10 | RAM-generated deterministic 6×1MiB, checksum ngoài network timing | SPEC§3; METRICS§1–2; G01/G05 |
| 11 | Resource↔QUIC stream; Open/Accept loop, goroutines; response size/data/close | PROTOCOL META/data/FIN/close; P4/G04 |
| 12 | Main TCP baseline một connection nhiều logical resources; multiple TCP optional | SPEC§4; CONTEXT§4; G03 |
| 13 | Header QB01 24 bytes, type/flags/reserved/id/offset/len, REQUEST/DATA/FIN/ERROR | PROTOCOL§1–2; META extension C08; G02 |
| 14 | TCP interleaving chunk16KiB round-robin; demux theo resource; ordered byte gap | PROTOCOL§5; THEORY; G03/G11 |
| 15 | Một TCP writer; không goroutines Write xen header/payload; producers/queue concept | PROTOCOL§5: RAM scheduler không bắt buộc queue dư thừa |
| 16 | TCP TLS1.3 vs QUIC TLS1.3; same certificate/ALPN; local self-signed | SPEC§5; TLS config/cert tests G00/G02 |
| 17 | QUIC listener/accept/streams, client dial; raw QUIC không HTTP/3 | SPEC; VERSIONS API checklist; P4 |
| 18 | Same-process ticket/cache, DialEarly/Allow0RTT, actual Used0RTT, rejection handling | SPEC§6; P10/G10; C04/C14 |
| 19 | Client t0/tConn/tReq/tFirst/tDone/tAll; monotonic; goodput | METRICS tất cả formulas; G05 |
| 20 | earlyReady/earlyWrite/handshake timeline, gửi trước handshake | METRICS; C04–05; G10/G11 packet corroboration |
| 21 | runs.csv một run/row; metadata/timings/0RTT/success/error; không actual expected numbers | METRICS§4 và schema; G06 |
| 22 | streams.csv một logical resource/row; ID, actual stream ID, byte/checksum/timings | METRICS§4; G06 |
| 23 | Bench tự động nhiều run, shell quản netem/root, Go runner quản trial | NETWORK§6, CLI schedule/entry/merge; P9 |
| 24 | Scenarios baseline/rtt50 loss0/1/3, 20Mbit, giống hai transport | configs/scenarios.json; G08/G09 |
| 25 | qlog config/QLOGDIR, .sqlog, qvis packet/ACK/loss/RTT/congestion/streams | NETWORK§8; version API check; P11/G11 |
| 26 | Wireshark minh họa UDP/Initial/Handshake/1RTT; tcpdump; không primary metric | NETWORK§8; DEMO; G11 |
| 27 | Make setup/build/server/demo-baseline/loss/0rtt/capture/cleanup | CLI target table; P12/G12 |
| 28 | Overall bench→client/server→network→CSV/qlog/pcap architecture | SPEC diagram; results layout; G07–G11 |
| 29 | Phase0–12: skeleton, workload, TCP, mux, QUIC, metrics, CSV, net, impair, runner, early, evidence, live | PLAN giữ 13 phase, gates/file responsibilities |
| 30 | Live5–7min: topology/UDP/main loss/early/summary; pre-run30; không kết luận một sample | DEMO_SCRIPT timeline + fallback; P12 |
| 31 | SPEC quan trọng, README chạy, DEMO_SCRIPT trình bày; đủ kiến trúc trước code | INDEX + các contracts tách theo trách nhiệm; prompt/TASK để IDE tiếp tục |

Các con số terminal/CSV trong chat là giả lập minh họa. Gói không giữ chúng dưới dạng results; originals/chat references giữ ý nghĩa, benchmark phải tạo số thật.

## 3. Đối chiếu T03 — 21 phần

| Phần gốc | Nội dung | Trạng thái trong handoff |
|---|---|---|
| 1–3 | QUIC stack, TCP limitations, independent streams/HOL | THEORY, SPEC; code TCP mux/QUIC |
| 4 | Connection/stream/frame/packet và bảng frames | THEORY + nguyên văn nguồn; không tự parser QUIC |
| 5 | ACK/loss/RTT/PTO, retransmit information trong packet mới | THEORY/Q&A; qlog evidence; thư viện thực hiện |
| 6 | Flow control khác congestion control | THEORY; manifest config/CC; không tự CC |
| 7 | TLS integration và encryption levels | SPEC/TLS; qlog/pcap; THEORY |
| 8 | 0-RTT prior state, reject, replay | SPEC/P10/ACCEPTANCE |
| 9 | CID và network path migration | THEORY; extension code chưa làm |
| 10 | Loss effects/multi-resource tốt hơn single file | SPEC main workload; evidence caveat |
| 11 | Architecture, 10 resource ví dụ, optional multi-TCP | Baseline final 6 theo chat; optional giữ backlog |
| 12 | Go+quic-go, không tự implement QUIC | SPEC/D01/P0 |
| 13 | Impairment RTT/loss/jitter/reorder, E RTT100-loss3,20–50 trials | NETWORK; 4 main+extension; defaults30 |
| 14 | Establishment/first app data/throughput/per-stream completion | METRICS phân biệt goodput và wire throughput |
| 15 | Demo A UDP/B early/C multiplex loss | SPEC/DEMO/G11 |
| 16 | QUIC vs HTTP/3, T03 không T09 | SPEC/Theory, non-goals |
| 17 | Không luôn thắng, user-space/kernel/offload/UDP-blocking trade-offs | REPORT requirements/manifest/limitations |
| 18 | Sơ đồ tổng hợp, recovery/ordering | THEORY; references nguyên bản |
| 19 | 10 câu Q&A | THEORY§2 đầy đủ |
| 20 | Câu chuyện kết nối toàn topic | THEORY outline / originals |
| 21 | Đúng phạm vi môn, mechanisms và benchmark thực | CONTEXT/SPEC/ACCEPTANCE |
| References/note | RFC9000/9001/9002/9114/9308, quic-go/netem, 3 câu tránh sai | REFERENCES/THEORY + originals |

## 4. Đối chiếu PHẦN 1 — toàn bộ đầu mục

| Phần | Nội dung giữ lại | Đích |
|---|---|---|
| 1,1.1,1.2 | General-purpose secure transport, UDP, QUIC≠HTTP3 | THEORY và SPEC |
| 2.1 | TCP+TLS handshake, 0RTT/prior state | SPEC/METRICS/P10 |
| 2.2 | Ordered TCP/multiplex/HOL | PROTOCOL TCP + THEORY |
| 2.3 | 4-tuple/CID/NAT rebinding/path validation | THEORY; scope extension |
| 2.4 | Kernel/user space, middlebox/ossification/UDP fallback | THEORY; không fallback ngầm trong benchmark |
| 3.1–3.5 | Connection state, uni/bidi+ID bits, frames, packet number≠offset, coalescing | THEORY, PROTOCOL distinction, trace requirements |
| 4.1–4.4 | Multiplexing, ordering independence nhưng shared congestion | G03/G04/G11 + report caveats |
| 5.1–5.6 | Recovery, flow, congestion, TLS, migration, versioning | THEORY; thư viện implement; manifest |
| 6,6.1,6.2 | Comparison/trade-offs và performance conditional | METRICS/NETWORK/REPORT |
| 7 | Mental model tổng hợp | THEORY outline, source retained |
| 8 | 8 câu tránh sai | THEORY/Q&A + code/report guardrails |
| 9 | Tổng kết / chuẩn bị chuyên sâu | THEORY + nguồn nguyên vẹn |
| References1–6 | RFC9000/9001/9002/9114/8999/9308 | REFERENCES, originals |

## 5. Kiểm soát hoàn thành

Mỗi row coding map tới gate; mỗi concept lý thuyết map tới source/defense. Nội dung optional được nêu rõ chứ không biến mất. Agent trước final phải đọc lại bảng này, kiểm acceptance evidence và ghi deviations vào CONTEXT. Không coi “đã copy file nguồn” là “agent đã hiểu”; cần đọc đủ nguồn liên quan khi giải quyết ambiguity/conflict/provenance hoặc final traceability và có explanation/code tests tương ứng khi triển khai; không bắt đọc lại toàn bộ originals mỗi phiên thường lệ.

P9 checkpoint 2026-10-01: rows1/19/21–24/29 được triển khai trong bench plan/entry/merge + shell orchestrator + cohort/stats/plots/manifest (D23). Software/actual localhost tests có evidence/p9; **G09 actual main240+16 và namespace interruption/cleanup còn BLOCKED** do sudo authentication trước runner. Không map plan256 hoặc localhost plots thành main performance evidence; không đánh dấu rows25/26 hoặc 0-RTT/HOL proof hoàn tất.

## 6. Superseding runtime/workflow decision — 2026-09-30

D13 thay môi trường ban đầu bằng Ubuntu WSL2 trên Windows 11 sau preflight netns/veth/netem/IFB/mirred thành công do người dùng cung cấp; tcpdump available. Chi tiết quan sát ở VERSIONS. Giữ nguyên conversation/handoff provenance 2026-09-28, originals và source manifests. Không coi preflight là G07/G08; topology, ingress IFB/mirred, protocol/metrics/CSV/evidence/demo và acceptance giữ nguyên. D14 thay mặc định autonomous bằng human-gated theo phase. Lượt này chỉ migration tài liệu, không thực thi P0–P12.


Closure actual P9/G09: User full G09 rerun 2026-10-01 tại results/p9-g09-8dFdkj PASS (g09_exit=0): main256 invoked/256 success/0 failure/0 missing, 240 measured+16 warmup/1536 resource rows; controlled SIGINT child130/cleanup0. Agent read-only audit/hash tại docs/evidence/p9/g09-rerun-review.json; không tự nhận chạy sudo. Dừng human review P9, không P10. Interactive terminal Ctrl+C qua tee từng exit141/cleanup1 vẫn là issue riêng, không được coi đã sửa bởi controlled child PASS.
