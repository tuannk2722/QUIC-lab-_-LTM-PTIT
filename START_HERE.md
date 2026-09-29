# Bắt đầu — QUIC Performance Lab / T03

Bộ bàn giao dành cho Codex trong IDE, phiên bản 1.0, ngày 28/09/2026 (Asia/Ho_Chi_Minh).
Đây là **đặc tả + cấu trúc khởi đầu để triển khai**, chưa phải chương trình QUIC đã viết hoặc benchmark đã chạy.

## Bạn cần làm gì?

1. Môi trường thực thi đã chọn: **Ubuntu VM**. Có thể mở IDE trong VM hoặc kết nối IDE vào VM. Agent chạy terminal/build/test/network ở Ubuntu; build binary Windows rồi chạy trong VM là sai môi trường.
2. Cho agent triển khai các phase theo tài liệu. Chỉ những thao tác hệ thống bị môi trường chặn mới cần bạn thực hiện thủ công; agent phải tiếp tục phần còn làm được và ghi rõ bước đang bị chặn.

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

Đã đọc toàn bộ nội dung 3 tệp đính kèm. Đã đối chiếu phần trao đổi 31 mục có trong ngữ cảnh hiện tại. Tìm lại được: nhóm 3 người, bạn phụ trách Tổng quan QUIC và demo. Bạn đã xác nhận **Ubuntu VM** và **không có quyết định bổ sung** trong phần hội thoại bị lược bỏ.

Không có bản xuất nguyên văn của phần chat bị lược bỏ; không tuyên bố đã đọc được phần không được cung cấp. Bảng truy vết và quyết định nằm tại [CONTEXT_AND_DECISIONS.md](docs/CONTEXT_AND_DECISIONS.md) và [TRACEABILITY.md](docs/TRACEABILITY.md).
