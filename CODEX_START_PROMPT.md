Hãy triển khai end-to-end dự án QUIC Performance Lab cho topic T03 môn Lập trình mạng, dựa trên bộ handoff trong workspace này.

Đầu tiên đọc AGENTS.md, docs/00-INDEX.md, .codex/TASK.md rồi toàn bộ đặc tả chuẩn tắc và nguồn gốc theo thứ tự được yêu cầu. Không bỏ qua phần protocol, metric, benchmark fairness, 0-RTT rejection, tiêu chí nghiệm thu và bảng đối chiếu context. Kiểm tra repo hiện có trước khi tạo/sửa file; không ghi đè code hoặc chỉ dẫn có sẵn một cách mù quáng.

Môi trường đã chốt là Ubuntu VM. Sản phẩm là CLI network lab bằng Go + quic-go: TCP/TLS multiplex một connection so với QUIC nhiều stream, workload chung, Linux namespace/veth/netem, benchmark/CSV/biểu đồ, qlog/PCAP và live demo 5–7 phút. Không tự chuyển thành web app hoặc HTTP/3.

Thực hiện P0–P12, tự tiếp tục sau mỗi phase đạt gate. Chốt phiên bản Go/quic-go tương thích ở P0, xây code thật, kiểm tra đúng các acceptance criteria. Không dừng ở scaffold hoặc viết lại plan. Nếu lệnh đặc quyền hoặc môi trường bị chặn, ghi chính xác nguyên nhân và các lệnh cần tôi chạy, đồng thời hoàn thành những phần độc lập còn lại. Không báo hoàn tất nếu nghiệm thu thực nghiệm chưa chạy.

Dùng docs làm source of truth; giữ .codex/TASK.md cập nhật để phiên sau tiếp tục. Quyết định triển khai nhỏ có thể tự xử lý và ghi lại; hỏi tôi khi có mâu thuẫn ảnh hưởng phạm vi/mục tiêu chưa được tài liệu giải quyết. Không bịa dữ liệu, không chọn riêng kết quả đẹp, không đặt mục tiêu QUIC luôn nhanh hơn TCP.

Cuối cùng bàn giao code chạy được, README tái lập được, kết quả benchmark thật và biểu đồ, evidence cho demo, bảng nghiệm thu kèm lệnh/output, DEMO_SCRIPT.md, giải thích phục vụ vấn đáp và khai báo AI. Bắt đầu bằng kiểm tra môi trường và P0 ngay sau khi đọc đầy đủ tài liệu.
