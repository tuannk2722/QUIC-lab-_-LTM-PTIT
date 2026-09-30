# Acceptance — điều kiện nghiệm thu

Chỉ ghi PASS khi đã chạy/kiểm chứng, kèm command, exit status, môi trường và path bằng chứng. `NOT_RUN` không bằng PASS. Gói handoff ban đầu tất cả gate thực thi đều NOT_RUN.

| ID | Điều kiện | Bằng chứng cần lưu |
|---|---|---|
| G00 | Toolchain/module pin, Ubuntu WSL2 preflight, 3 binaries build, SAN đúng | VERSIONS, build log, cert inspect, doctor report |
| G01 | Bytes/checksum workload deterministic; bounds trước allocate | Unit output + workload manifest |
| G02 | QB01/TLS single-resource correctness, partial reads/writes, verify cert | Tests/real transfer; bad cert failure |
| G03 | TCP 1 connection/6 logical resources, round-robin single writer | Scheduler frame order test + integration result |
| G04 | QUIC 1 connection/6 actual streams; listeners cùng port; hash đúng | Stream map + real results + race test |
| G05 | Client monotonic metric semantics; không first-byte sau full chunk | Timing hook review/test và formulas |
| G06 | Typed JSON/CSV, null/errors/FK/count/flush handling | Actual success/failure datasets + validator output |
| G07 | Namespace topology/UID/ownership/idempotence/interrupt cleanup | System logs; host state comparison |
| G08 | IFB placement thực, RTT/rate/loss config/counters đúng | Network-state snapshots + measured probes |
| G09 | Main 240 measured+16 warmup, statistics và failures đầy đủ | Raw/shards/schedule/summary/plots/manifest |
| G10 | Cold/resumed/early thực; ticket signal; rejection retry đúng | 3 mode results + forced rejection test + attempts |
| G11 | PCAP/qlog/progress usable; chứng minh UDP/early; HOL được giải thích đúng | Capture/trace and annotated evidence notes |
| G12 | Fresh reproduction, Make demo, rehearsal 5–7 phút, docs/disclosure đầy đủ | ACCEPTANCE_RESULTS + README + report/rehearsal |

Capability preflight netns/veth/netem/IFB/mirred do người dùng báo PASS ngày 2026-09-30 chỉ xác nhận primitives có sẵn. Tại migration, G00–G12 đều NOT_RUN; trạng thái thực thi P0 mới nhất ở [ACCEPTANCE_RESULTS.md](ACCEPTANCE_RESULTS.md). G07/G08 cần toàn bộ bằng chứng thực theo bảng, không được suy ra từ preflight hoặc build.

## Các điều kiện chi tiết không được bỏ qua

**Protocol:** read boundaries không đồng nhất frame boundaries; unknown length/header bị reject trước allocate; malformed offsets/size/duplicate FIN và EOF trước FIN fail; cancellation/unresponsive peers terminate bounded; stream/cert errors không panic cả server tùy ý; no goroutine leak trong integration.

**TCP baseline:** không 6 connections masquerading as one; không sequential whole-file serving; TLS1.3 được verify và key/cert như QUIC. Dùng round-robin cho app layer, không tuyên bố packet scheduling giống QUIC.

**QUIC:** reliable streams (không DATAGRAM); native ID lưu thật; không global response writer lock; resource checksum/bytes đúng; stream limits đủ; batch barrier không deadlock khi missing request. Loss/flow/congestion do library, không tự thêm retransmit ở app để thay QUIC semantics.

**0-RTT:** accepted evidence cần kết hợp actual Used0RTT sau successful handshake + request enqueue trước observed handshake + trace packet 0-RTT chứa app request. Timing alone không đủ. Lần đầu no ticket không được ghi true. Server ListenEarly/accept behavior đúng version. Rejection test thực, fallback một lần trên read-only workload, không mất/đếm đôi bytes; mode và actual state tách riêng. Không hứa first response time=0.

**Network:** main profile ingress-ifb; UDP/TCP cùng conditions; no-loss median RTT tolerance theo NETWORK; direction loss ghi rõ; IFB/counter/filter working; offload/CC và trạng thái host/execution layer (WSL2), distro/kernel, CPU/RAM/swap lưu. Nói configured loss probability, không fake empirical packet loss rate. Không downgrade silently khi IFB thiếu.

**Data:** success iff đủ bytes + FIN + hash; lỗi CSV write làm command fail; full failure denominator; every planned resource has row even on failure. No nan/inf/negative duration. Main goodput units/sanity check; checksums sau tAll. 6 correlated streams không thành 6 independent statistical trials.

**Evidence:** instrumentation off trong performance suite, on trong evidence suite, manifest phân biệt. HOL cơ chế: dữ liệu sau TCP gap bị giữ và QUIC stream khác có thể tiến triển khi có missing range; packet chứa nhiều streams/shared congestion được nêu. Nếu trace không chứng minh được causal claim, ghi INCONCLUSIVE, không tô thành PASS “proof”; phần chức năng qlog/capture có thể PASS riêng. Để claim full demo complete, thu trace đạt hoặc nêu rõ outstanding requirement.

**Presentation:** nhóm giải thích được 10 Q&A gốc và semantics code họ dùng; technical source citations; AI usage disclosure không bịa human review. Outline/report phục vụ trình bày; không tự nộp bài/nhắn giảng viên.

## Mẫu ACCEPTANCE_RESULTS agent phải tạo

| ID / subcase | Status | Command / cách kiểm | Expected | Actual | Evidence path | Remaining issue |
|---|---|---|---|---|---|---|
| G00 | NOT_RUN | Điền lệnh thực sau khi chạy | Pin/build | Chưa chạy | — | — |

Cần tách subcase khi gate vừa có pass vừa có blocked (ví dụ G11-PCAP PASS, G11-HOL INCONCLUSIVE). Không gộp để che trạng thái. Final user report nêu scope hoàn tất và các gate chưa đạt, không “mọi thứ xong” khi mới chạy unit tests.
