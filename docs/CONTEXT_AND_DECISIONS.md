# Context và quyết định

## 1. Nguồn và mức độ xác nhận

- Người dùng học môn Lập trình mạng; topic T03. Nhóm **3 người**; người dùng phụ trách **Phần 1 Tổng quan QUIC và demo**.
- Yêu cầu hiện tại: gói tài liệu/cấu trúc đưa thẳng vào IDE để Codex triển khai end-to-end đúng kỳ vọng; giữ mọi ý đã thảo luận; hỏi khi thiếu thông tin quan trọng.
- Trong lượt bàn giao này, người dùng chọn **Ubuntu VM** và xác nhận **không có thêm quyết định** trong phần đầu hội thoại bị lược bỏ.
- Go, quic-go, CLI, 6 resource, topology và các API trước đây là đề xuất của assistant. Yêu cầu “cho ra output đúng kỳ vọng theo các ý trên” được hiện thực hóa thành **baseline thiết kế của bộ handoff này**, không ghi sai rằng người dùng đã tự chốt từng thông số.
- Chưa biết deadline cụ thể, phiên bản Ubuntu/VMware, cấu hình VM và repo Classroom. Không tự bịa; agent khảo sát ở P0. Đây không cản việc thiết kế, nhưng ảnh hưởng thời gian chạy benchmark và lệnh cài đặt.
- Không có transcript nguyên văn đầy đủ của phần bị lược bỏ. Các 31 mục hiện thấy được tổng hợp ở TRACEABILITY; cả 3 tài liệu được giữ nguyên và kiểm checksum. Đây là giới hạn provenance, không phải lý do tự loại requirement hiện có.

## 2. Baseline cần triển khai

| ID | Quyết định | Lý do / trạng thái |
|---|---|---|
| D01 | Raw QUIC qua quic-go, Go; TCP + TLS 1.3 đối chứng | Bám T03; không tự triển khai RFC hoặc HTTP/3 |
| D02 | CLI, terminal, CSV/chart, Wireshark, qlog/qvis | Demo network; GUI chỉ là mở rộng sau |
| D03 | Ubuntu VM; hai namespace qclient/qserver | Người dùng đã chọn VM; không tạo hai VM |
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
