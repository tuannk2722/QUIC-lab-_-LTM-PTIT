# Khai báo sử dụng AI

Tài liệu technical topics yêu cầu công khai phần nào được AI hỗ trợ và nhóm phải giải thích/bảo vệ được code.

## Tình trạng ban đầu

Bộ handoff/spec/protocol/metrics/plan này được tạo với hỗ trợ của ChatGPT/Codex từ tài liệu người dùng, phần thảo luận hiện có và đối chiếu nguồn kỹ thuật chính thức. Người dùng chọn Ubuntu VM và xác nhận không có quyết định bổ sung ở phần chat thiếu. **Chưa có code ứng dụng hoặc benchmark được thực hiện trong lượt tạo handoff.**

## Agent cần cập nhật theo thực tế

| Ngày | Công cụ/model nếu biết | File/chức năng được hỗ trợ | AI làm gì | Con người đã kiểm gì | Test/evidence |
|---|---|---|---|---|---|
| 2026-09-28 | ChatGPT/Codex | Bộ handoff/docs/config/schema | Tổng hợp, đặc tả và lập kế hoạch | Chọn môi trường; chưa xác nhận review toàn bộ code | Kiểm tra gói tài liệu; không có benchmark |

Không điền rằng nhóm đã review hiểu code khi chưa diễn ra. Thêm phần implementation theo phase thực tế. Khi lấy library/examples, ghi nguồn/license riêng, không biến attribution thư viện thành “tự implement QUIC”.
