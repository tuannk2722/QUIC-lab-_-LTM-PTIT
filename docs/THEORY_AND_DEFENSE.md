# Kiến thức giữ lại và chuẩn bị vấn đáp

Tài liệu T03 và các nguồn môn được giữ nguyên trong [references/originals](references/originals/); [TRACEABILITY](TRACEABILITY.md) đối chiếu cả phần Tổng quan/PHẦN 1 của thiết kế trao đổi. Phần này nối kiến thức với code/evidence, không xác nhận nhóm đã hiểu hoặc bảo vệ code. Dữ liệu và giới hạn hiện hành ở [REPORT](REPORT.md); P11 actual G11 đã PASS, G12 theo [ledger](ACCEPTANCE_RESULTS.md).

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

Sửa cách hiểu dễ quá mức từ nguồn: flow control/congestion control hỗ trợ vận hành transport nhưng không thay cơ chế ACK/loss/retransmission tạo reliability; không phải mọi packet QUIC (ví dụ Version Negotiation/Retry) đều có cùng packet number/protection như data packets. Initial protection không có tính bí mật trước người quan sát như 1-RTT. Lab không tự tái triển khai các cơ chế này. Nguồn kỹ thuật: [RFC9000 streams/packets/retransmission](https://www.rfc-editor.org/rfc/rfc9000.html), [RFC9001 TLS/early-data](https://www.rfc-editor.org/rfc/rfc9001.html), [RFC9002 recovery/CC](https://www.rfc-editor.org/rfc/rfc9002.html); APIs thực phải theo [VERSIONS](VERSIONS.md).

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

## 4. Outline và assets cho slides

Người dùng phụ trách Tổng quan và demo; phân bổ nội dung phần hai thành viên còn lại cần nhóm phối hợp. Bảng dưới là outline có assets thật, chưa là slide deck hoàn thành/nộp. Chọn số slide theo phân công; [DEMO_SCRIPT](DEMO_SCRIPT.md) điều khiển phần live 5–7 phút.

| Nội dung | Một điều cần người nghe nhớ | Asset/source có thể đưa lên slide |
|---|---|---|
| QUIC trong stack, QUIC≠HTTP/3 | UDP là substrate; lab T03 dùng raw transport/application QB01 | [Architecture](DEMO_SPEC.md), T03§1/§16 và RFC9000§1 |
| Vì sao thiết kế QUIC | Setup/TLS, một ordered byte stream, CID/path, user-space evolution và trade-offs | Bản đồ§1; T03§2/§9/§17; migration ở đây là lý thuyết |
| Connection→stream→frame→packet→datagram | QB01 app frame khác QUIC STREAM frame; packet có thể chứa nhiều streams | [PROTOCOL](PROTOCOL.md), native stream mapping trong actual run; RFC9000§2/§12 |
| Testbed và phép so sánh | Một connection mỗi transport, cùng6MiB payload/IFB conditions; CUBIC/Reno và kernel/userspace khác | [Topology/conditions](NETWORK_AND_BENCHMARK.md), [P9 manifest](../results/p9-g09-8dFdkj/main/manifest.json) |
| UDP/QUIC thật | PCAP nhận diện UDP4433, Initial/Handshake/1-RTT; đây là sample đã thu | [handshake_cold viewer](../results/p11-g11-6a8cc99602b7/viewers/handshake_cold.html), [PNG](../results/p11-g11-6a8cc99602b7/viewers/handshake_cold.png), paired PCAP trong cùng root |
| Ordering HOL dưới loss | TCP byte gap chặn toàn ordered stream; sibling QUIC progress được quan sát trước gap recovery | [loss_0_tcp PNG](../results/p11-g11-6a8cc99602b7/viewers/loss_0_tcp.png), [loss_0_quic PNG](../results/p11-g11-6a8cc99602b7/viewers/loss_0_quic.png), [witness notes](../results/p11-g11-6a8cc99602b7/evidence-notes.md) |
| Cold/resumed/early | Ticket là prior state; early request đi sớm, response không phải0ms; rejection/replay có giới hạn | [P10 handshake plot](../results/p10-g10-cR1oR9/main/plots/handshake_ms.png), [early viewer](../results/p11-g11-6a8cc99602b7/viewers/handshake_early.html), [REQUEST proof](../results/p11-g11-6a8cc99602b7/early-packet-check.json) |
| Kết quả và giới hạn |30 samples/nhóm, full denominator/failures; performance phụ thuộc workload/testbed/implementation | [P9 total plot](../results/p9-g09-8dFdkj/main/plots/total_ms.png), [REPORT tables](REPORT.md), [AI disclosure](AI_USAGE.md) |

Assets P9/P10 là performance cohort; P11 là instrumented evidence. Khi dùng backup nói rõ **pre-recorded**, root/run_id/scenario/seed; timeline bars chỉ minh họa progress, causal witnesses lấy packet/qlog/ACK/ranges. Giữ captions/n/units/failures của plots. Không kết luận “QUIC nhanh vì UDP” hoặc “QUIC luôn nhanh hơn”.

Technical depth30%, implementation25%, presentation25%, Q&A20% là [rubric topic](references/originals/network-programing-topic.md), khác trọng số toàn môn trong [INT1433](references/originals/INT1433_HKI_2026_2027.txt). Source duration tổng15–20 phút có các phần10–12 technical+5–7 demo+3–5 Q&A có thể vượt tổng; nhóm cần thống nhất cách tính khi trình bày thật. Slides+demo-script là deliverables do nhóm nộp, repo không tự upload.

## 5. Những điểm code và evidence cần review cùng nhóm

| Điểm cần tự giải thích | Code/test/evidence để mở trong IDE |
|---|---|
| Header bounds, partial I/O và META→DATA*→FIN | [codec](../internal/protocol/codec.go), [receiver](../internal/protocol/response.go), [protocol tests](../internal/protocol/protocol_test.go) và [PROTOCOL](PROTOCOL.md) |
| Vì sao TCP chỉ một writer nhưng QUIC không global response-write lock | [TCP round-robin](../internal/transport/tcp/scheduler.go)/[test](../internal/transport/tcp/scheduler_test.go), [QUIC server](../internal/transport/quic/server.go)/[streams](../internal/transport/quic/streams.go) |
| t0/first DATA byte/FIN cuối/hash và goodput | [metrics timer](../internal/metrics/timer.go)/[test](../internal/metrics/timer_test.go), [client read hooks](../internal/transport/quic/client.go), [METRICS](METRICS_AND_RESULTS.md) |
| Ticket notification, actual state và one-replay coordinator | [RunSession](../internal/transport/quic/early.go), [client engine](../internal/transport/quic/client.go), [six-worker rejection test](../tests/integration/early_test.go), [attempt publication](../internal/bench/session.go) |
| REQUEST API enqueue chưa là packet proof | `handshake_early` actual Used0RTT/DidResume, REQUEST end trước observed handshake; decrypted frame14/PN0/stream0/32bytes và server receive qlog trong [G11 checker](../results/p11-g11-6a8cc99602b7/g11-check.json) |
| HOL candidate đủ điều kiện nào, chọn pair ra sao | [conservative detector](../analysis/hol.py), [checker](../tests/system/check_g11.py): first qualifying pair0/all10 retained; ACK/SACK vs pre-IFB eth0 tap; sampling16KiB/margin3ms |
| Vì sao statistical samples là trials, failures giữ denominator | [summarizer](../analysis/summarize.py), [P9/P10 summaries](REPORT.md); p95 nearest-rank/sample SD n−1, resource distributions tách theo ID |
| Privilege/ownership/cleanup, frozen source/build receipt | [NETWORK](NETWORK_AND_BENCHMARK.md), [Makefile](../Makefile), [build helper](../scripts/build.py), [P12 reproduction receipt](evidence/p12/README.md) |
| Vì sao build có TLS keylog overlay và giới hạn của nó | D28/VERSIONS, [hash-checked generator](../scripts/tls_keylog_overlay.py), [early-secret tests](../tests/integration/early_keylog_test.go); thêm optional export, không custom cryptography |

Hai witness để tự kể được: TCP `loss_0_tcp` gap3187438027/SACK/ACK237→253 và retry248; QUIC `loss_0_quic` lost PN25/stream20/resource6/range[1345,2602), later PN30, resource5 deliver16384bytes trước recovery PN50. Không định danh resource từ encrypted TCP bytes; QUIC stream độc lập ordering vẫn dùng shared congestion/path. Bảng và detector giúp nhóm kiểm tra câu trả lời; test PASS không chứng nhận human understanding.
