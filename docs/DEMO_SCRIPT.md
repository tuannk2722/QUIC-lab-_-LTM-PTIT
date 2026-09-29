# Kịch bản live 5–7 phút

Trạng thái: runbook theo hợp đồng; agent phải thay path/command cụ thể và gắn evidence thật sau P12. Không có kết quả đo sẵn trong bản này.

## Trước buổi trình bày

Build/cert/dependencies xong offline; Ubuntu VM được cấp resource cố định và không chạy workload nền nặng. Doctor/network preflight pass. Chuẩn bị trước raw/plots/report từ 30 repeats, PCAP/qlog xem được, một trace HOL có giải thích, trace 0-RTT accepted và rejection test. Đóng hết trial trước đổi profile. Không trình diễn cài thư viện tại lớp.

| Thời gian | Thao tác | Giải thích / bằng chứng |
|---|---|---|
| 0:00–0:40 | Hiện topology, workload, manifest phiên bản | Một VM, hai namespace, cùng resource, TCP/TLS và raw QUIC |
| 0:40–1:30 | `make demo-quic-basic`; mở PCAP đã thu | UDP4433, Initial/Handshake/1-RTT; payload mã hóa; đây không phải HTTP/3 |
| 1:30–3:30 | `make demo-loss`; mở progress/trace tiêu biểu | 6 logical transfers, một connection mỗi transport, loss downstream; completion không tự chứng minh causal HOL |
| 3:30–4:45 | `make demo-0rtt` trên handshake profile | Cold không ticket; warm-up/cache; resumed vs early; actual Used0RTT, handshake timeline, packet evidence |
| 4:45–5:40 | Hiện summary/plots từ 30 repeats | n, median/p95, fail rate, units; live sample không đại diện toàn bộ |
| 5:40–6:20 | Nêu bốn quan sát và limitation | UDP substrate, native streams, ordering khác dưới loss, early-data có điều kiện |

`demo-*` wrappers tự quản lý server profile và readiness; không gõ 20 lệnh network thủ công. Nếu phải dùng server đã chạy, kiểm profile phù hợp trước chuyển bulk→handshake.

## Lời giải thích trọng tâm

- “Chúng em dùng cùng payload, certificate, network condition và số connection; TCP app layer round-robin, QUIC native streams. Kết quả vẫn phụ thuộc scheduler, CC và kernel/userspace.”
- “QUIC tránh ordering HOL giữa các stream. Nó không làm mất gói biến mất, không loại HOL trong stream và vẫn chia sẻ congestion response.”
- “0-RTT là khả năng gửi request sớm khi có prior session state; không phải phản hồi trong 0 ms. Chúng em kiểm trạng thái và packet, không chỉ thấy DialEarly trả nhanh.”
- “Live run là một sample. Kết luận dựa trên cohort nhiều lượt, kể cả failures; không đặt giả thuyết QUIC luôn nhanh hơn.”

## Dự phòng trung thực

- Live loss không hiện pattern rõ: dùng trace thật đã lưu có run_id/time/config và nói rõ pre-recorded; không rerun liên tục chỉ đến khi QUIC thắng.
- Live early rejected/missing ticket: hiện trạng thái đúng; giải thích fallback; dùng evidence accepted đã lưu để minh họa, không đổi false→true.
- qvis không đọc schema hoặc mạng web không có: dùng viewer đã kiểm tra/offline screenshot có attribution. Không đổi đuôi file để giả chuyển format.
- VM/tool permission lỗi: báo đang dùng kết quả thực nghiệm đã ghi, không nói chạy live. Cleanup nguồn lab, giữ logs.
- Chỉ có 5 phút: bỏ qlog navigation trực tiếp, giữ bốn ý chính; packet/trace screenshot đã chuẩn bị. Demo duration không bao gồm full 240-run suite.

## Gắn với thời lượng môn học

Tài liệu môn ghi tổng 15–20 phút, đồng thời 10–12 phút technical +5–7 demo +3–5 Q&A có thể vượt tổng. Giữ nguyên nguồn, hỏi giảng viên cách tính Q&A khi chuẩn bị buổi thật; không tự sửa yêu cầu. Có thể rehearsal 10 technical +5 demo +3 Q&A =18 phút trong khung nếu Q&A nằm trong tổng. Đây là phân bổ đề xuất, không lịch được giảng viên xác nhận.
