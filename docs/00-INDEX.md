# 00 — Bản đồ tài liệu / Source of truth

## Đọc lần đầu

| Thứ tự | Tệp | Vai trò |
|---|---|---|
| 1 | [CONTEXT_AND_DECISIONS.md](CONTEXT_AND_DECISIONS.md) | Mục tiêu, quyết định, đề xuất cũ và giới hạn context |
| 2 | [DEMO_SPEC.md](DEMO_SPEC.md) | Hệ thống phải làm gì; invariant và phạm vi |
| 3 | [PROTOCOL.md](PROTOCOL.md) | QB01 framing, state machine và stream lifecycle |
| 4 | [METRICS_AND_RESULTS.md](METRICS_AND_RESULTS.md) | Timestamp, công thức, dữ liệu và thống kê |
| 5 | [NETWORK_AND_BENCHMARK.md](NETWORK_AND_BENCHMARK.md) | Topology, đặc quyền, impairment và thí nghiệm |
| 6 | [CLI_CONTRACT.md](CLI_CONTRACT.md) | Flags, targets, exit code, output |
| 7 | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Phase/file/thứ tự migration và gate |
| 8 | [ACCEPTANCE.md](ACCEPTANCE.md) | Bằng chứng cần có để báo done |
| 9 | [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | Live 5–7 phút và phương án dự phòng |
| 10 | [THEORY_AND_DEFENSE.md](THEORY_AND_DEFENSE.md) | Kiến thức cần giải thích và outline trình bày |
| 11 | [TRACEABILITY.md](TRACEABILITY.md) | Đối chiếu toàn bộ nguồn/chat với đầu ra |
| 12 | [REFERENCES.md](REFERENCES.md), [AI_USAGE.md](AI_USAGE.md), [VERSIONS.md](VERSIONS.md) | Nguồn kỹ thuật, disclosure và khóa toolchain |
| 13 | `references/originals/` | Toàn bộ 3 file nguồn, giữ nguyên |

## Quy tắc áp dụng

Các file 1–9, config và schema là chuẩn tắc của lab. THEORY cung cấp cách giải thích; references là dữ liệu nguồn, không tự mở rộng scope coding. Thứ tự ưu tiên: yêu cầu hiện tại của người dùng → quyết định rõ ràng trong CONTEXT → hợp đồng chuyên biệt → DEMO_SPEC → ví dụ trao đổi trước → tài liệu tham khảo.

Nếu chuẩn tắc mâu thuẫn nhau: sửa đồng bộ và ghi quyết định, không âm thầm chọn. Không thay user scope chỉ vì một tài liệu tham khảo có thêm tính năng. Các thay đổi kỹ thuật so với ví dụ ban đầu đều phải đọc ở CONTEXT.

- Sửa transport: PROTOCOL + DEMO_SPEC + acceptance liên quan.
- Sửa đo lường/CSV: METRICS + schema + analysis + acceptance liên quan.
- Sửa runner/network: NETWORK + CLI + config + acceptance liên quan.
- Phiên mới: luôn đọc AGENTS + INDEX + `.codex/TASK.md`; sau đó đọc lại phần đang làm.
- Trước tuyên bố done: đối chiếu toàn bộ ACCEPTANCE và TRACEABILITY.

## Artifact có sẵn / cần tạo

Có sẵn: docs, config, schema, nguồn gốc, prompt và checkpoint. Cần tạo qua P0–P12: Go code, tests, shell wrappers, Makefile, analysis scripts và **tất cả dữ liệu thực nghiệm**. Không có số liệu benchmark mẫu giả trong gói này.
