# Kiểm tra bộ handoff trước bàn giao

Ngày: 28/09/2026 (Asia/Ho_Chi_Minh). Phạm vi: cấu trúc và tính nhất quán của tài liệu/config/schema.

- 5 tệp nguồn được giữ nguyên bytes và SHA-256; hai bản T03 trùng nội dung.
- JSON configs/schema đọc hợp lệ; JSON Schema được kiểm cấu trúc.
- Ba CSV header trong METRICS khớp schema: runs42, streams19, progress7 trường.
- Liên kết Markdown nội bộ của tài liệu mới trỏ tới file có trong gói; code fences đóng đủ.
- Config main suite: 4 scenarios ×2 transports ×30 measured =240; warm-ups16.
- Bulk payload: 6×1,048,576 =6,291,456 bytes.
- Bảng truy vết chứa cả31 mục trao đổi và các mục trong nguồn T03/PHẦN1/course.
- Có prompt đầu vào, checkpoint trạng thái, file map theo phase và acceptance.

**Không phải nghiệm thu phần mềm:** chưa có Go implementation, chưa build binaries, chưa chạy VM/netem/TCP/QUIC/0-RTT, chưa có số liệu hiệu năng. G00–G12 vẫn NOT_RUN trong IDE cho tới khi thực thi.
