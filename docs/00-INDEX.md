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
- Phiên mới: luôn đọc AGENTS + INDEX + `.codex/TASK.md`; sau đó đọc normative docs liên quan phase được user cho phép. Mặc định human-gated: chạy gate, cập nhật TASK và dừng review; chỉ tự nhiều phase khi user yêu cầu rõ ràng. Originals dùng khi ambiguity/conflict/provenance/final traceability, không bắt đọc lại toàn bộ mỗi phiên.
- Trước tuyên bố done: đối chiếu toàn bộ ACCEPTANCE và TRACEABILITY.

## Artifact có sẵn / cần tạo

Current: người dùng xác nhận P9/G09 PASS và cho phép riêng P10/G10. P10 implementation/functional/localhost evidence có tại [P10 runbook](evidence/p10/README.md); actual G10 ingress IFB BLOCKED do sudo authentication trước runner. Dừng review P10; P11/P12 chưa triển khai. [D24 audit](evidence/audit-p7-p9/README.md) giữ nguyên blocked attempts lịch sử; terminal Ctrl+C qua tee chưa được xác minh lại.

Có sẵn từ handoff: docs, config, schema và nguồn gốc. P0–P6 thêm toolchain/CLI/TLS/workload/QB01/TCP multiplex/QUIC cold/metrics/canonical JSON/CSV và validator. P7 namespace/veth/ifb0/ownership/UID/rollback có G07 rerun PASS sau recovery lỗi IFB host (log giữ nguyên). P8 có ingress IFB + egress-demo, kernel/offload/seed snapshots, metadata và G08 actual rerun PASS, tám trials/48 hashes và host-state/interrupt cleanup. P9 thêm runner/schedule/merge/manifest/stats/plots; actual user rerun PASS tại results/p9-g09-8dFdkj, đủ main240+16/1536 rows, controlled interrupt130/cleanup0 và agent audit/hash; xem evidence/p9. Interactive terminal Ctrl+C qua tee còn issue141/cleanup1 riêng.

P10 thêm ticket-cache notification, shared cold/resumed/early flow, ListenEarly/DialEarly và một rejection replay giữ t0/attempts; CLI/runner và analysis state classification. Handshake mặc định96 targets=90 measured+6 target warmups;64 prior ticket warm-ups ngoài aggregate; plots cold/resumed/early tách riêng, actual fallback giữ transfer outcome và bị loại khỏi accepted-mode latency. Actual G10 BLOCKED, không gán loopback impairment hoặc claim packet proof. Qlog/PCAP/progress, 0-RTT corroboration và đóng gói/rehearsal còn P11/P12. Không có số liệu giả; gate/evidence hiện hành ở ACCEPTANCE_RESULTS và TASK.
