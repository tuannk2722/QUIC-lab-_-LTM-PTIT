# QUIC Performance Lab

T03 — QUIC Protocol Implementation and Performance, môn Lập trình mạng, PTIT.

**Trạng thái ban đầu:** bộ handoff để coding; chưa có binary, source Go hoàn chỉnh hoặc kết quả thực nghiệm. Đọc [START_HERE.md](START_HERE.md) để dùng trong IDE.

Thiết kế: cùng bộ resource trong RAM được phục vụ bởi TCP/TLS multiplex và raw QUIC trên TCP/UDP 4433. Client chạy trong Ubuntu dưới WSL2 trên Windows 11 qua hai namespace có network impairment. Số liệu từ client được lưu theo run và resource; qlog và packet capture phục vụ giải thích cơ chế.

[Đặc tả](docs/DEMO_SPEC.md) · [Kế hoạch triển khai](docs/IMPLEMENTATION_PLAN.md) · [Nghiệm thu](docs/ACCEPTANCE.md) · [Kịch bản demo](docs/DEMO_SCRIPT.md)

Repo phải nằm trong filesystem Linux native, ưu tiên `/home/<user>/...`, không `/mnt/c/...` hoặc `/mnt/d/...`. Mở Windows VS Code bằng Remote WSL, workspace `WSL: Ubuntu`. Implementation mặc định human-gated: chỉ phase được người dùng cho phép, chạy gate rồi cập nhật TASK và dừng review. Migration tài liệu đã hoàn thành; P0/G00 chưa chạy.

## Hợp đồng README sau triển khai

Agent phải thay mục này bằng các bước **đã kiểm tra thực tế**, giữ lại lịch sử trạng thái nếu hữu ích:

1. Phiên bản OS/kernel, Go, quic-go và package hệ thống cần cài.
2. Clone/mở repo; build; tạo certificate; unit/integration tests.
3. Setup topology; server background và readiness; client TCP/QUIC.
4. Chạy từng demo và benchmark; tạo báo cáo/biểu đồ.
5. Xem CSV, qlog, PCAP; cách giải mã traffic demo nếu cần.
6. Dừng server, clear-netem, teardown; xử lý lỗi phổ biến và môi trường thiếu quyền.
7. Chỉ rõ lệnh chạy ở host Windows hay bên trong Ubuntu WSL2; mọi build/test/network/benchmark chạy trong Ubuntu WSL2.
8. Liên kết provenance, disclosure AI và giới hạn kết luận.

Các Make targets trong docs là hợp đồng cần implement, chưa tồn tại trong gói ban đầu này.
