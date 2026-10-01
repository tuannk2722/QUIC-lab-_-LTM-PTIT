# Context và quyết định

## 1. Nguồn và mức độ xác nhận

- Người dùng học môn Lập trình mạng; topic T03. Nhóm **3 người**; người dùng phụ trách **Phần 1 Tổng quan QUIC và demo**.
- Yêu cầu handoff ban đầu (2026-09-28): gói tài liệu/cấu trúc đưa thẳng vào IDE để Codex triển khai end-to-end đúng kỳ vọng; giữ mọi ý đã thảo luận; hỏi khi thiếu thông tin quan trọng.
- Trong lượt bàn giao ngày 2026-09-28, người dùng chọn **Ubuntu VM** và xác nhận **không có thêm quyết định** trong phần đầu hội thoại bị lược bỏ.
- Go, quic-go, CLI, 6 resource, topology và các API trước đây là đề xuất của assistant. Yêu cầu “cho ra output đúng kỳ vọng theo các ý trên” được hiện thực hóa thành **baseline thiết kế của bộ handoff này**, không ghi sai rằng người dùng đã tự chốt từng thông số.
- Tại handoff 2026-09-28, chưa biết deadline, phiên bản Ubuntu/VMware, cấu hình VM và repo Classroom. Quyết định môi trường cũ nay được D13 thay thế; quan sát máy hiện tại ở VERSIONS. Ubuntu release, toolchain và các thông tin còn thiếu cần xác minh ở P0, không tự bịa.
- Không có transcript nguyên văn đầy đủ của phần bị lược bỏ. Các 31 mục hiện thấy được tổng hợp ở TRACEABILITY; cả 3 tài liệu được giữ nguyên và kiểm checksum. Đây là giới hạn provenance, không phải lý do tự loại requirement hiện có.

## 2. Baseline cần triển khai

| ID | Quyết định | Lý do / trạng thái |
|---|---|---|
| D01 | Raw QUIC qua quic-go, Go; TCP + TLS 1.3 đối chứng | Bám T03; không tự triển khai RFC hoặc HTTP/3 |
| D02 | CLI, terminal, CSV/chart, Wireshark, qlog/qvis | Demo network; GUI chỉ là mở rộng sau |
| D03 | Quyết định gốc 2026-09-28: Ubuntu VM; hai namespace qclient/qserver | Phần môi trường được D13 supersede ngày 2026-09-30; topology giữ nguyên |
| D04 | Một connection mỗi transport, 6 × 1 MiB, chunk 16 KiB | Cùng workload; thể hiện concurrent resources |
| D05 | Một server process, hai listeners TCP/UDP :4433 | Dùng chung resource RAM/certificate |
| D06 | TCP một writer round-robin; QUIC một bidirectional stream/resource | Không giả multiplex bằng truyền tuần tự cả file |
| D07 | QB01 header 24 bytes; codec chung cho cả hai transport | Chốt wire contract và giảm chênh lệch framing |
| D08 | Metric chính ở client, thời gian monotonic | Không trừ clock server với client |
| D09 | 30 lượt đo/transport/scenario, 2 warm-up không tính | Nằm trong khuyến nghị 20–50; warm-up được gắn nhãn |
| D10 | 0-RTT read-only; warm-up ticket; cold/resumed/early riêng | Chứng minh thực sự và xử lý rejection |
| D11 | Không lấy localhost làm performance evidence | Localhost dùng correctness tests |
| D12 | Không đặt tiêu chí QUIC phải nhanh hơn | Kết luận dựa trên số liệu, fail rate và giới hạn |

## 3. Làm rõ/correct các ví dụ trước khi giao AI code

| ID | Điểm trong trao đổi cũ | Hợp đồng sau làm rõ |
|---|---|---|
| C01 | Server egress loss gọi là “data packet loss” | Loss này tác động mọi packet phù hợp hướng/filter, có cả handshake/control; không gọi data-only |
| C02 | Chỉ egress netem trên eth0 | Giữ profile demo egress; benchmark chính receiver ingress qua IFB do TSQ. Không xóa topology hai namespace |
| C03 | Chỉ nhìn thời gian hoàn tất để nói HOL | Cần progress và qlog/PCAP để giải thích; bar chart riêng chỉ là quan sát hiệu năng |
| C04 | Write trước HandshakeComplete “là bằng chứng trực tiếp” | Write chỉ xác nhận API nhận bytes; yêu cầu Used0RTT sau handshake và qlog/capture có packet 0-RTT |
| C05 | DialEarly return gọi connection established | Tách early_ready_ms và handshake_ms; connect_ms không dùng giá trị early-ready |
| C06 | TCP 30 lần rồi QUIC 30 lần | Xen kẽ thứ tự AB/BA có seed, chạy tuần tự từng trial; tránh bias theo thời gian |
| C07 | CSV TTFB có hai cách tính thay thế nhau | Ghi cả first_byte_ms từ t0 và ttfb_request_ms từ đầu gửi request, tên cố định |
| C08 | Header có Offset/Length nhưng chưa có state machine | Chốt big-endian, giới hạn, REQUEST/META/DATA/FIN/ERROR, EOF, timeout ở PROTOCOL |
| C09 | Mỗi QUIC goroutine mở stream → gán ID 0/4/8 giả định | Mở theo resource ID và lưu ID thực; không giả ID thành resource index |
| C10 | Hash ngoài timing từng resource | Đợi tất cả tDone rồi mới hash tất cả buffer, tránh hash R1 ảnh hưởng R2 đang nhận |
| C11 | Rate 20 Mbps nhưng CSV minh họa goodput ~60 Mbps | Loại số minh họa khỏi kết quả; đo thật, kiểm units và sanity bound |
| C12 | Phiên bản/API quic-go ngầm định | Khóa phiên bản ở P0, đọc source/go doc đúng tag; qlog API có thể đổi |
| C13 | Có TLS certificate nhưng chưa nói xác minh | CA/cert local có SAN, RootCAs; không tắt verify mặc định |
| C14 | 0-RTT có cache nhưng không đợi ticket | Quan sát cache Put với timeout; không sleep đoán rằng ticket đã tới |
| C15 | Benchmark runner áp netem nhưng “Go không root” | Shell orchestrator quản lý đặc quyền; Go bench ở namespace client, điều phối các lần đo |
| C16 | Ba docs được gợi ý là đủ | Tách hợp đồng chi tiết theo trách nhiệm để giảm context cần đọc lại; index/trace giữ liên kết |

Những mục C là quyết định kỹ thuật của bản handoff nhằm đóng khoảng trống implementation; không trình bày chúng như lời người dùng nguyên văn.

## 4. Phạm vi mở rộng được giữ lại nhưng chưa làm

Migration/NAT rebinding, nhiều TCP connections, RTT100-loss3, symmetric loss, jitter/reorder, workload khác, dashboard CSV: lưu như backlog, không vô tình biến thành tiêu chí bắt buộc. Lý thuyết migration/flow/congestion/TLS vẫn bắt buộc giải thích. Slides là yêu cầu môn học; bộ coding phải cung cấp outline/evidence phục vụ slides, không tự sinh slide có số liệu giả trước benchmark.

## 5. Quyết định mới sau handoff

Agent thêm ngày, vấn đề, lựa chọn, lý do, requirement ảnh hưởng, file thay đổi và bằng chứng. Không sửa lịch sử nguồn để làm như mọi thứ đã chốt từ trước.

### D13 — 2026-09-30: thay môi trường thực thi của D03

Quyết định hiện hành: Windows 11 host, Ubuntu dưới WSL2 thay Ubuntu VMware VM ban đầu. Người dùng báo đã kiểm chứng netns (tạo/xóa qclient/qserver), veth (tạo/xóa), netem (gắn qdisc 50 ms), IFB (tạo device/UP), act_mirred (load module); tcpdump có sẵn. Quan sát phiên bản/tài nguyên/path cụ thể lưu ở VERSIONS; agent không chạy lại preflight trong migration này. Capability PASS chỉ xác nhận primitives, không tương đương G00/G07/G08 hoặc benchmark hợp lệ.

Chỉ thay execution layer/testbed: giữ Go/quic-go raw QUIC CLI, TCP/TLS một connection multiplex, QUIC một connection/stream mỗi resource, workload deterministic, qclient/qserver/veth/tc/netem, ingress IFB/mirred chính, metric/CSV/schema, benchmark methodology, qlog/PCAP, resumption/0-RTT/rejection, demo và acceptance semantics. Repo trên native Linux filesystem; Remote WSL là cách mở IDE. Requirements ảnh hưởng: môi trường G00, manifest G05/G06, testbed G07/G08 và runbook G12; không giảm gate.

### D14 — 2026-09-30: human-gated mặc định

Thay workflow tự chạy P0→P12 bằng chỉ phase/milestone được user cho phép rõ ràng. Chạy gate đầy đủ, cập nhật TASK, dừng review; chỉ tự nhiều phase/end-to-end khi user yêu cầu rõ ràng. Phiên mới đọc AGENTS/INDEX/TASK và normative docs liên quan phase; originals dùng khi ambiguity/conflict/provenance/final traceability. Giữ source-of-truth discipline và mục tiêu cuối P0–P12; build riêng lẻ không phải gate pass.

D13/D14 được đồng bộ trong AGENTS, start prompt/README/START_HERE, TASK, INDEX, NETWORK, VERSIONS, PLAN, ACCEPTANCE, METRICS, DEMO_SCRIPT, TRACEABILITY và AI_USAGE. Migration chỉ tài liệu; implementation và toolchain pin chưa bắt đầu.

### D15 — 2026-09-30: refinement trong P0 được cho phép

- Pin Go 1.27.1 và quic-go v0.63.0 (minimum Go 1.26.0); cài Go local trong `.tools/`, không sudo build/download, không commit tự động. Đã đối chiếu official metadata, checksum, source đúng tag và compile smoke; xem VERSIONS và evidence/p0.
- Module local `quic-performance-lab` theo PLAN: remote repository không được coi là đã xuất bản Go module. Make giới hạn build parallelism 2 cho tài nguyên hiện có, không phải thông số kiến trúc benchmark.
- Ba mains dùng internal/cli chung; TLS config chung nằm trong internal/tlsconfig/config.go. Không sinh data/hash workload trước P1, không mở socket/transfer hoặc tạo schedule. Thao tác chưa có trả 1, input lỗi trả 2.
- Input bounds bổ sung ở CLI§5 bảo vệ config parser và tránh duration overflow; giữ nguyên workload/scenario chính và schema results. Unknown/duplicate JSON keys bị từ chối. Đây là refinement validation, không đổi thí nghiệm.
- Doctor inventory không root tách khỏi scripts/preflight-network.sh đặc quyền chỉ dùng namespace tạm riêng. Probe không thực hiện G07/G08; lượt agent ban đầu bị chặn ở xác thực sudo. Sau đó người dùng chạy probe thành công lúc 2026-09-30T04:48:25Z; agent đối chiếu log/script và lưu evidence/p0/network-probe.log cùng provenance/hash, đóng G00 PASS. Lịch sử lỗi quyền được giữ nguyên. Các phần độc lập có PASS riêng trong ACCEPTANCE_RESULTS.
- Certificate EC P-256 tự ký dùng làm trust anchor local, SAN cố định theo SPEC, hạn 30 ngày, quyền 0600; tạo lại cần --force rõ ràng. Không commit cert/private key. API qlog và congestion implementation ghi VERSIONS để tránh dùng nhầm API cũ.

### D16 — 2026-09-30: chi tiết QUIC cold P4/G04

- Một process chuẩn bị TCP listener và QUIC UDP listener cùng số port trước readiness; hai listener nhận cùng `*workload.Store` và TLS certificate config. Một semaphore tối đa 8 active connections chia sẻ giữa transport để giữ DEMO_SPEC§3. `--ready-file` công bố bằng hard link atomically trong cùng thư mục, từ chối marker có sẵn; xóa marker do process vừa tạo khi dừng bình thường. Files: `internal/cli/cli.go`, `internal/transport/tcp/server.go`.
- quic-go v0.63.0 chạy QUIC v1 cold qua `Dial`/`Listen`; server nhận tối đa 64 client-initiated bidirectional streams, client từ chối server-initiated bidirectional streams; cả hai từ chối incoming unidirectional streams. Receive credits khởi đầu/tối đa: stream 512 KiB/2 MiB, connection 2 MiB/16 MiB. Đây là sliding flow-control window, không tạo buffer theo tổng credits. Timeout idle handshake đặt bằng một nửa handshake bound cấu hình vì pinned quic-go cho phép tối đa 2× idle timeout; client cũng có dial deadline riêng. Files: `internal/transport/quic/{config,client,server,streams}.go`, `docs/VERSIONS.md`.
- Native `StreamID()` được lưu theo ResourceID; không suy ID từ thứ tự. QUIC request writers chạy sau khi mở đủ N streams; server batch barrier xác nhận REQUEST và send-half EOF trước response, các response workers ghi độc lập. Đây là refinement của PROTOCOL§3/§6 và G04, không triển khai 0-RTT P10, CSV P6 hay benchmark G09. Evidence/trạng thái cuối ở `docs/ACCEPTANCE_RESULTS.md`.

### D17 — 2026-09-30: kết quả cold trial đơn lẻ P5/P6

- `time.Time` được giữ trong client đến khi tính Sub; first DATA byte được ghi ở callback read đầu, không sau nguyên chunk. `total_ms` dừng ở FIN cuối; `elapsed_ms` có thể gồm verify/cleanup. TCP dial success được ghi cả khi TLS handshake fail, mốc handshake thiếu giữ null. Đây là cách áp dụng METRICS§1–2, không đổi công thức.
- Một invocation cold client tạo một thư mục kết quả mới, với raw JSON trước CSV, writer đồng bộ và lỗi flush/close trả nonzero. ID tự sinh có timestamp UTC + random suffix; ID user nhập được giới hạn ký tự path-safe. Không append vào directory có sẵn. Trường 0-RTT/TLS-resumption chưa quan sát ở P10 giữ nullable thay vì bịa false; `attempted_0rtt=false` cho cold. Dữ liệu P6 chỉ là localhost correctness, network_profile `loopback-test`, chưa có manifest full/cohort/benchmark; P9 hoàn thiện phần đó theo METRICS§3–5.

### D18 — 2026-09-30: sửa audit P0–P6

- QUIC resolution dùng context của trial; t0 bắt đầu trước resolve/socket setup như phạm vi TCP Dial. Buffer/config vẫn chuẩn bị trước t0. Setup failure giữ N slots và start/end để ghi failed trial. Không có phép trừ wall clocks hay reset t0.
- Result nội bộ phân biệt checksum chưa kiểm/đúng/sai và lỗi từng resource. Sau khi mọi reader dừng (success hoặc failure), verify các resource đã FIN; tiếp tục kiểm siblings khi một hash sai. Run vẫn fail nếu bất kỳ resource/cleanup lỗi; resource đã verify và cleanup hợp lệ giữ success riêng. TCP cleanup lỗi áp dụng mọi resource trên shared connection; QUIC cleanup được ghi theo worker.
- Validator từ chối INCOMPLETE, kiểm kiểu raw JSON chính xác, stream milestones/order/end và QUIC ID bắt buộc trên successful stream. Không ép first_byte >= request_end. Không đổi schema v1, không triển khai phase mới.

### D19 — 2026-09-30: ownership/lifecycle cho P7

- Topology P7 cố định `qclient`/`qserver`, veth `eth0`, `ifb0` up; marker root-owned ở `/run/quic-performance-lab/topology-v1` gắn UID/GID người gọi sudo với device:inode của hai namespace. `setup` idempotent chỉ khi marker và trạng thái topology khớp; collision không marker bị từ chối, không xóa tên chỉ vì trùng tên. Failure/INT/TERM rollback namespace vừa tạo theo identity; SIGKILL không thể trap và cần kiểm thủ công nếu xảy ra.
- Entry root chỉ dùng cho `ip netns exec`, sau đó `setpriv` hạ về UID/GID thường trước server/client. `teardown` từ chối namespace có PID, thay vì kill process không biết có thuộc lab hay không. Với `make server` foreground ở P7, dừng bằng Ctrl+C trước `make clean-network`; system runner quản lý PID riêng để kiểm interrupt. `make clean-network` chưa là manager cho detached server/capture của các phase sau. Các script không sửa host NIC/routes hoặc tự chạy netem; G07 traffic và host-state vẫn phải kiểm thực trước PASS. Files: `scripts/network/{common,setup,teardown}.sh`, `scripts/run-in-netns.sh`, `Makefile`, `tests/system/run.sh`; requirements NETWORK§2/§6, CLI§3, PLAN P7, ACCEPTANCE G07.

### D20 — 2026-10-01: IFB module tạo thiết bị host trong lần G07 đầu

- User chạy system runner G07 trong Ubuntu WSL2. Collision, rollback, topology, UID drop và ping hai chiều có log thực, nhưng host link comparison FAIL trước transfer: nạp IFB ngầm với mặc định `numifbs=2` tạo `ifb0`/`ifb1` trong `init_net`. Teardown xóa hai namespace, còn IFB host tồn tại. Đây là lỗi của P7, không phải số liệu benchmark hay G07 PASS. Nguồn giải thích driver: [Linux `drivers/net/ifb.c`](https://github.com/torvalds/linux/blob/master/drivers/net/ifb.c); snapshots/log ở `results/p7-g07-JqV32x/host-state/` và `docs/evidence/p7/g07-system.log`.
- Sửa setup nạp `ifb` bằng `modprobe ifb numifbs=0` trước khi tạo IFB namespace và kiểm host link không đổi ngay sau nạp. Không xóa IFB host chung trong teardown. Script recovery một lần chỉ cho phép xóa hai IFB DOWN/noop khi link/address/route hiện tại khớp snapshot lỗi và chỉ hai thiết bị này khác baseline; kiểm IFB identity và host tc filters, recheck trước từng lần xóa, cho phép tiếp tục sau partial delete, rồi đối chiếu lại snapshot baseline. Recovery và G07 rerun cần sudo tương tác của người dùng; static/precheck không thay actual gate. Requirements NETWORK§2/§6, PLAN P7, ACCEPTANCE G07. Files: `scripts/network/{setup,teardown,restore-host-ifb}.sh`, docs/evidence P7.
