# Kiến thức giữ lại và chuẩn bị vấn đáp

Hai tài liệu T03 và PHẦN 1 được giữ nguyên trong references/originals. Phần này chỉ nối kiến thức với code/evidence cần trình bày, không thay thế tài liệu nghiên cứu.

## 1. Bản đồ nội dung

| Kiến thức từ tài liệu | Cần hiểu và liên hệ demo |
|---|---|
| QUIC general-purpose transport trên UDP | Chọn raw QUIC; UDP substrate không tự đem lại reliability hoặc tốc độ |
| TCP/TLS setup so QUIC integrated TLS | Cold handshake/TTFA; t0 tới secure readiness khác thời gian request transfer |
| Một TCP ordered byte stream | QB01 interleaving vẫn nằm trong một byte sequence; missing gap chặn bytes sau |
| Streams bidirectional/unidirectional và 62-bit ID | Lab dùng client bidi, actual IDs 0/4/8…; không đồng nhất ID resource |
| Connection → stream → frame → packet → datagram | QB01 frame là app format; QUIC STREAM frame là format transport, hai loại khác nhau |
| Packet chứa nhiều frame/streams; datagram coalescing | Không khẳng định 1 stream=1 packet=1 UDP datagram |
| ACK, packet/time thresholds, PTO, loss recovery | Dùng thư viện; data cần thiết vào packet mới với packet number mới |
| Flow control connection/stream và MAX_* | Credit bảo vệ receiver; không nhầm với số stream hoặc congestion window |
| Congestion control, cwnd/RTT/bytes-in-flight/ECN | Loss vẫn ảnh hưởng shared path; CC của hai implementations phải được ghi |
| TLS1.3, CRYPTO, Initial/Handshake/0-RTT/1-RTT | Không có TLS record layer trên QUIC giống TLS/TCP; packet protection có exceptions và levels |
| Session resumption và replay risk | Read-only requests; ticket/cache/ALPN; rejected early và retry riêng |
| Connection ID, NAT rebinding, migration | Connection identity không chỉ 4-tuple; path validation và CID rotation; lý thuyết, chưa demo |
| User space, versioning, ossification, middleboxes | Lợi ích tiến hóa và CPU/offload/UDP-blocking trade-offs |
| QUIC ≠ HTTP/3 | HTTP/3 là app trên QUIC (T09 riêng); không triển khai HTTP stack cho T03 |
| Performance có điều kiện | Không guarantee QUIC nhanh hơn; phải nêu workload/testbed và failure rate |

Sửa cách hiểu dễ quá mức từ nguồn: flow control/congestion control hỗ trợ vận hành transport nhưng không thay cơ chế ACK/loss/retransmission tạo reliability; không phải mọi packet QUIC (ví dụ Version Negotiation/Retry) đều có cùng packet number/protection như data packets. Initial protection không có tính bí mật trước người quan sát như 1-RTT. Lab không tạo parser các packet này nên không tự tái triển khai chúng.

## 2. Mười câu hỏi gốc, câu trả lời ngắn

1. **UDP không reliable, tại sao QUIC streams reliable?** QUIC layer quản lý ACK/loss detection và gửi lại thông tin cần thiết; stream offsets cho phép reassemble ordered bytes. UDP chỉ chuyển datagrams.
2. **Vì sao không chỉ sửa TCP?** QUIC kết hợp streams/TLS/CID/versioning với triển khai user space; TCP deployment và middleboxes làm thay đổi lớn khó hơn, không có nghĩa TCP không thể cải tiến.
3. **QUIC loại mọi HOL?** Không. Tránh cross-stream ordering HOL; trong stream vẫn ordered, app dependencies vẫn có thể chặn.
4. **Một packet tương ứng một stream?** Không. Packet có thể chứa frames của nhiều streams; mất nó có thể ảnh hưởng nhiều stream.
5. **Có gửi lại nguyên packet number cũ?** Không tái dùng packet number cũ để retransmit. Thông tin cần phục hồi đi trong packet mới.
6. **Có congestion control?** Có. Streams cùng connection/path vẫn chịu congestion response chung.
7. **0-RTT dùng lần đầu?** Không khi không có prior session state. DialEarly không tự tạo ticket từ không khí.
8. **Vì sao không early mọi thao tác?** Replay risk, rejection và resumption constraints. Lab chỉ đọc resource, không mutation nghiệp vụ.
9. **QUIC và HTTP/3 giống nhau?** Không; HTTP/3 dùng QUIC. Demo là raw transport/application protocol riêng.
10. **Loss A không ảnh hưởng B?** B không phải đợi gap A do global ordering, nhưng shared congestion/network và packet chứa cả A/B vẫn ảnh hưởng.

## 3. Câu hỏi code/benchmark nhóm phải giải thích

- Header tại sao 24 bytes? Big-endian, payload length, offset, META/FIN kiểm toàn vẹn ra sao?
- Vì sao một writer TCP? Multiple Write có thể được API đồng bộ nhưng không tự tạo frame atomicity/scheduling fairness theo design.
- Tại sao batch barrier ở cả hai transport? Giảm chênh lệch thời điểm tập resource sẵn sàng; không lock response toàn connection QUIC.
- Đo byte đầu ở đâu? Trong callback Read DATA payload đầu tiên; không dùng lúc header tới hoặc full-chunk read xong.
- Vì sao checksum sau tất cả tDone? Để hash một resource không chiếm CPU làm sai thời gian các resource còn tải.
- Same workload có nghĩa fair tuyệt đối? Không, CC/scheduler/kernel/userspace/TLS/offload khác; nêu kiểm soát được gì và còn confounders nào.
- Vì sao dùng receiver IFB? Tránh sender-local TSQ interaction của netem làm lệch TCP performance; phải verify path chứ không chỉ thêm qdisc.
- Same seed có cùng losses? Không, packetization khác. Seed hỗ trợ tái lập trong giới hạn cùng implementation/config.
- 0-RTT accepted chứng minh thế nào? Actual connection state + timing + packet/stream evidence. Write return chỉ là API enqueue.
- Fallback sau rejection có reset timer? Không; giữ end-to-end t0 và attempts history.
- Goodput khác throughput? Chỉ resource payload/duration, không wire overhead; MiB khác MB, Mbps khác MB/s.
- Vì sao 30 repeats, và p95 có hạn chế? Để quan sát variability; p95 của mẫu nhỏ không phải tail estimate mạnh cho Internet chung.

## 4. Outline phục vụ slides, không phải slide deck đã hoàn thành

Người dùng phụ trách Tổng quan và demo; không chiếm nội dung phần của hai thành viên khác mà chưa phối hợp. Tổng quan đề xuất: (1) QUIC trong stack và QUIC≠HTTP3; (2) bốn hạn chế TCP/TLS và lý do thiết kế; (3) connection/stream/frame/packet; (4) HOL với caveat shared congestion; (5) bản đồ TLS/recovery/flow/congestion/CID/versioning và trade-offs. Chọn số slide theo phân công, không áp số slide cố định không có trong yêu cầu.

Demo slides/assets lấy topology, manifest/conditions, chart và trace thật. Technical depth 30%, implementation 25%, presentation25%, Q&A20% là rubric topic từ nguồn, khác trọng số đánh giá toàn môn trong INT1433. Không nhập hai bộ trọng số thành một.
