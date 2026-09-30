# Bắt đầu — QUIC Performance Lab / T03

Bộ bàn giao dành cho Codex trong IDE, phiên bản 1.0, ngày 28/09/2026 (Asia/Ho_Chi_Minh).
Bản gốc là **đặc tả + cấu trúc khởi đầu**. Cập nhật 2026-09-30: P0/G00 đến P6/G06 PASS; TCP/TLS và raw QUIC cold batch 6 resource trên một connection mỗi transport, cùng số port TCP/UDP; metrics client và canonical JSON/CSV cho cold trial. P5/P6 chờ human review; chưa có network benchmark. Bằng chứng ở ACCEPTANCE_RESULTS, lệnh chạy localhost ở README.

## Bạn cần làm gì?

1. Môi trường hiện hành từ 2026-09-30: **Ubuntu dưới WSL2 trên Windows 11**. Windows VS Code là UI, mở bằng Remote WSL với workspace `WSL: Ubuntu`; terminal/build/test/network chạy trong Ubuntu WSL2. Repo phải nằm trên filesystem Linux native, ưu tiên `/home/<user>/...`, không `/mnt/c/...` hoặc `/mnt/d/...`.
2. Cho phép rõ ràng từng phase/milestone. Mặc định HUMAN-GATED: agent chỉ làm phase được phép, chạy gate, cập nhật TASK rồi dừng review; build thành công riêng lẻ không đủ. Chỉ tự tiếp tục nhiều phase khi người dùng yêu cầu rõ ràng. Khi bị chặn, agent ghi BLOCKED/lệnh thủ công và làm phần độc lập trong phạm vi được phép. Người dùng đã approve P0/G00 và P4/G04, cho phép P5/G05 rồi P6/G06; sau G06 dừng review.

Không cần dán lại toàn bộ cuộc trò chuyện. `AGENTS.md` chỉ cách đọc; `docs/00-INDEX.md` chỉ nguồn sự thật; `.codex/TASK.md` giữ tiến độ qua phiên. Context quan trọng phải nằm trong file, không phụ thuộc trí nhớ phiên chat.

## Kết quả cuối cùng cần nhận

- Client/server Go chạy thật: TCP + TLS 1.3 multiplex và raw QUIC nhiều stream.
- Cùng workload 6 × 1 MiB, một connection mỗi transport, kiểm tra toàn vẹn.
- Hai Linux namespace, veth, netem; benchmark chính dùng ingress/IFB và có kiểm tra cấu hình thực tế.
- Demo traffic UDP/QUIC; multiplexing dưới packet loss; cold/resumed/0-RTT và đường xử lý 0-RTT bị từ chối.
- CSV theo run/resource, biểu đồ từ số liệu thật, qlog, PCAP, manifest môi trường và báo cáo giới hạn.
- Make targets để chạy; hướng dẫn tái lập; kịch bản live 5–7 phút; câu hỏi vấn đáp và khai báo AI.

“Hoàn tất” phải đạt [ACCEPTANCE.md](docs/ACCEPTANCE.md), không chỉ `go build` thành công. Không đặt điều kiện QUIC phải thắng TCP.

## Tình trạng context

Đã đọc toàn bộ nội dung 3 tệp đính kèm. Đã đối chiếu phần trao đổi 31 mục có trong ngữ cảnh hiện tại. Tìm lại được: nhóm 3 người, bạn phụ trách Tổng quan QUIC và demo. Trong handoff ngày 2026-09-28, bạn đã xác nhận **Ubuntu VM** và **không có quyết định bổ sung** trong phần hội thoại bị lược bỏ.

Quyết định môi trường ban đầu được D13 (2026-09-30) thay bằng WSL2 sau capability preflight thành công; xem VERSIONS. Đây không phải G07/G08 pass.

Không có bản xuất nguyên văn của phần chat bị lược bỏ; không tuyên bố đã đọc được phần không được cung cấp. Bảng truy vết và quyết định nằm tại [CONTEXT_AND_DECISIONS.md](docs/CONTEXT_AND_DECISIONS.md) và [TRACEABILITY.md](docs/TRACEABILITY.md).
