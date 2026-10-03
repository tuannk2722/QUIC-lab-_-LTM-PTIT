# Kịch bản live 5–7 phút

P12 executable runbook, 2026-10-03 (Asia/Saigon). G00–G12 actual PASS; G12 results/p12-g12-51c13b94f99b live360.000794s và baseline preparation177.218539s riêng trước live, full checkerPASS/g12_exit0; không claim human oral delivery. Full command `bash scripts/run-g12-review.sh`; [P12 evidence](evidence/p12/README.md). Các demo-* tự start server/capture đúng profile, giữ artifacts và clear/teardown. Dependency/build/cert chuẩn bị trước theo README, không download trong live.

## Trước buổi trình bày

Build/cert/dependencies xong offline; Ubuntu WSL2 có giới hạn tài nguyên được ghi và giữ ổn định; Ubuntu WSL2 và host Windows không chạy workload nền nặng. Doctor/network preflight pass. Chuẩn bị trước raw/plots/report từ 30 repeats, PCAP/qlog xem được, một trace HOL có giải thích, trace 0-RTT accepted và rejection test. Đóng hết trial trước đổi profile. Không trình diễn cài thư viện tại lớp.

D31: gate chạy `make demo-baseline` trước khi bắt đầu đồng hồ live; đây vẫn là actual mandatory acceptance với TCP+QUIC/probes/captures/cleanup đầy đủ. `preparation.json` giữ duration/log/hash và được bind vào `rehearsal.json`; software và baseline preparation không nằm trong300–420s live. Live giữ đúng A→C→B→summary; tất cả transfer/decode/proof/cleanup của ba demos live vẫn tính giờ. D30 đã đưa baseline vào live khiến user-run423s FAIL; không sửa timing cũ hoặc nới giới hạn. Các mốc trong bảng là runbook cho người trình bày; driver đợi mốc tối thiểu, không cắt command còn chạy. Overrun vẫn FAIL nếu tổng>420s.

| Thời gian | Thao tác | Giải thích / bằng chứng |
|---|---|---|
| 0:00–0:40 | Hiện topology, workload, manifest phiên bản | Một môi trường Ubuntu WSL2, hai namespace, cùng resource, TCP/TLS và raw QUIC |
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
- WSL2/tool permission lỗi: báo đang dùng kết quả thực nghiệm đã ghi, không nói chạy live. Cleanup nguồn lab, giữ logs.
- Chỉ có 5 phút: bỏ qlog navigation trực tiếp, giữ bốn ý chính; packet/trace screenshot đã chuẩn bị. Demo duration không bao gồm full 240-run suite.

## Gắn với thời lượng môn học

Tài liệu môn ghi tổng 15–20 phút, đồng thời 10–12 phút technical +5–7 demo +3–5 Q&A có thể vượt tổng. Giữ nguyên nguồn, hỏi giảng viên cách tính Q&A khi chuẩn bị buổi thật; không tự sửa yêu cầu. Có thể rehearsal 10 technical +5 demo +3 Q&A =18 phút trong khung nếu Q&A nằm trong tổng. Đây là phân bổ đề xuất, không lịch được giảng viên xác nhận.

## Assets thật để mở trước khi lên lớp

- UDP/QUIC và accepted early: `results/p11-g11-6a8cc99602b7/viewers/handshake_early.html` hoặc PNG/SVG cùng basename; paired decrypted REQUEST frame14,PN0,native stream0,32-byte QB01 request ở `early-packet-check.json`. TLSResumed/Used0RTT=true,request_end1.945624ms<observed handshake56.605283ms.
- HOL representative: cùng root `viewers/loss_0_tcp.html`/`loss_0_quic.html`, `g11-check.json` (representative pair và detailed run witnesses), `evidence-notes.md` và exact witness paths ở [REPORT](REPORT.md). TCP ACK237/retry248/advancingACK253; QUIC lostPN25/stream20/resource6, sibling resource5 progress trước recoveryPN50. Không suy cause từ completion bars.
- Main bulk plots/report: `results/p9-g09-8dFdkj/main/plots/`, attempted240 measured+16warmup,256 success/0failure. Handshake: `results/p10-g10-cR1oR9/main/plots/`,90measured+6targetwarmup và64prior ticket riêng.
- Public backup khi không có original local: P9/P10/P11 archives trong `docs/evidence/`, raw/config/provenance/PNG/SVG/offlineHTML có run_id thật. P11 archive không chứa secrets/PCAP/large PDML; để decode cần local original. Always label pre-recorded. [Slide outline/Q&A/ownership](THEORY_AND_DEFENSE.md).

Actual G12 đã ghi commands và live360.000794s, đạt300–420s; [closure audit](evidence/p12/g12-rerun-review.json). Đây là timed terminal walkthrough, không chứng nhận spoken delivery. Người trình bày tự rehearsal lời nói và lựa chọn mở viewer/plot phù hợp. Browser rendering và video recording chưa được agent xác nhận; không tự ghi nhận đã nộp deck.
