# Bắt đầu — QUIC Performance Lab / T03

Current D24 audit fix P7–P9: 5 findings đã sửa, software/race/localhost PASS; actual G09 bản sửa BLOCKED ở sudo authentication. [Evidence và next commands](docs/evidence/audit-p7-p9/README.md). Trạng thái dataset PASS bên dưới là lịch sử của source cũ, không là gate bản sửa.

Bộ bàn giao dành cho Codex trong IDE, phiên bản 1.0, ngày 28/09/2026 (Asia/Ho_Chi_Minh).
Bản gốc là **đặc tả + cấu trúc khởi đầu**. Cập nhật 2026-10-01: P0/G00 đến P8/G08 PASS; cold TCP/QUIC, metrics/CSV, topology và impairment receiver IFB đã chạy thật. G08 rerun exit0/cleanup0 với tám successful evidence trials; [Evidence P8](docs/evidence/p8/README.md) có log và artifact review. P9 runner/manifest/stats/plots và software checks đã xong; G09 actual user rerun PASS tại results/p9-g09-8dFdkj, đủ main240+16; controlled interrupt/cleanup verified. Interactive terminal Ctrl+C qua tee còn issue141/cleanup1 đã ghi evidence. Dừng human review P9; 0-RTT/qlog thuộc phase sau.

## Bạn cần làm gì?

1. Môi trường hiện hành từ 2026-09-30: **Ubuntu dưới WSL2 trên Windows 11**. Windows VS Code là UI, mở bằng Remote WSL với workspace `WSL: Ubuntu`; terminal/build/test/network chạy trong Ubuntu WSL2. Repo phải nằm trên filesystem Linux native, ưu tiên `/home/<user>/...`, không `/mnt/c/...` hoặc `/mnt/d/...`.
2. Cho phép rõ ràng từng phase/milestone. Mặc định HUMAN-GATED: agent chỉ làm phase được phép, chạy gate, cập nhật TASK rồi dừng review; build thành công riêng lẻ không đủ. Chỉ tự tiếp tục nhiều phase khi người dùng yêu cầu rõ ràng. Khi quyền/OS chặn, agent ghi BLOCKED/lệnh thủ công và hoàn tất phần độc lập trong phase được phép. Người dùng đã cho phép riêng P9/G09; sau cập nhật evidence thì dừng review, không tự mở P10.

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

Đường chạy P8 trong Ubuntu WSL2: `make setup-network`; `make netem SCENARIO=rtt50-loss0`; `make -s inspect-network > PATH`; server foreground `make server PROFILE=bulk`, client qua `scripts/run-in-netns.sh` và `--network-state=PATH`. Clear bằng `make clear-netem`, dừng server rồi `make clean-network`. Toàn bộ G08: `sudo bash tests/system/run.sh --gate G08`; xem README để lưu exit/evidence. Không dùng capability preflight hay localhost regression thay G08.

Không có bản xuất nguyên văn của phần chat bị lược bỏ; không tuyên bố đã đọc được phần không được cung cấp. Bảng truy vết và quyết định nằm tại [CONTEXT_AND_DECISIONS.md](docs/CONTEXT_AND_DECISIONS.md) và [TRACEABILITY.md](docs/TRACEABILITY.md).

## P9/G09 — actual PASS / dừng review

[P9 runbook/evidence](docs/evidence/p9/README.md) ghi behavior, files, software verification, limitation và full manual G09 command. Sau build/deps/certs bằng user và topology/server absent, chạy `sudo bash tests/system/run.sh --gate G09` trong terminal Ubuntu WSL2; capture exit/log như README. Không dùng localhost hoặc schedule256 chưa chạy thay main performance cohort. Runner tự managed server/process cleanup, giữ failures và source shards; review AB/BA/seed reset, missing-row denominator, watcher/signals/UID, network before-after và stats p95/sample stddev.
