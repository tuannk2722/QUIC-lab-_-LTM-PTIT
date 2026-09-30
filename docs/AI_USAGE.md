# Khai báo sử dụng AI

Tài liệu technical topics yêu cầu công khai phần nào được AI hỗ trợ và nhóm phải giải thích/bảo vệ được code.

## Tình trạng ban đầu

Bộ handoff/spec/protocol/metrics/plan này được tạo với hỗ trợ của ChatGPT/Codex từ tài liệu người dùng, phần thảo luận hiện có và đối chiếu nguồn kỹ thuật chính thức. Trong handoff 2026-09-28, người dùng chọn Ubuntu VM và xác nhận không có quyết định bổ sung ở phần chat thiếu. **Chưa có code ứng dụng hoặc benchmark được thực hiện trong lượt tạo handoff.**

## Agent cần cập nhật theo thực tế

| Ngày | Công cụ/model nếu biết | File/chức năng được hỗ trợ | AI làm gì | Con người đã kiểm gì | Test/evidence |
|---|---|---|---|---|---|
| 2026-09-28 | ChatGPT/Codex | Bộ handoff/docs/config/schema | Tổng hợp, đặc tả và lập kế hoạch | Chọn môi trường; chưa xác nhận review toàn bộ code | Kiểm tra gói tài liệu; không có benchmark |
| 2026-09-30 | Codex | Agent instructions, start workflow và docs môi trường/manifest/TASK | Migration sang WSL2 theo D13, human-gated theo D14; giữ lịch sử gốc | Người dùng cung cấp preflight/observations đã kiểm chứng; chưa xác nhận review bản migration | Search/classification, diff review và git diff --check; không chạy application gates, không pin Go/quic-go |
| 2026-09-30 | Codex | P0: module, CLI/config/TLS, Make/scripts/tests, docs và TASK | Inspect repo/env, pin từ nguồn chính thức, implement skeleton, chạy build/config/CLI/SAN/API checks, ghi G00 BLOCKED phần sudo | Người dùng cho phép riêng P0; chưa review code P0 | docs/ACCEPTANCE_RESULTS.md và docs/evidence/p0/; không workload P1/transfer/benchmark |

| 2026-09-30 | Codex | Đóng hồ sơ P0: evidence, acceptance, versions, README/START_HERE, TASK | Đối chiếu log/script, lưu provenance/hash, cập nhật G00 PASS, giữ lỗi quyền lịch sử | Người dùng trực tiếp chạy probe thành công trong WSL2; chưa xác nhận review toàn bộ code | network-probe.log và network-probe-provenance.json; không chạy lại tests đã đạt, không P1 |

Không điền rằng nhóm đã review hiểu code khi chưa diễn ra. Thêm phần implementation theo phase thực tế. Khi lấy library/examples, ghi nguồn/license riêng, không biến attribution thư viện thành “tự implement QUIC”.
