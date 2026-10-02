# Bắt đầu — QUIC Performance Lab / T03

Current: P10/G10 PASS; P11 D28 early export và D29 sysctl/PATH repair PASS software/actual metadata. Latest full user-run FAIL trước trial0/23; patched full G11 cần terminal sudo: `bash scripts/run-g11-review.sh`. [P11 evidence](docs/evidence/p11/README.md); không P12.

Bộ bàn giao dành cho Codex trong IDE, phiên bản 1.0, ngày 28/09/2026 (Asia/Ho_Chi_Minh).
Bản gốc là **đặc tả + cấu trúc khởi đầu**. Cập nhật 2026-10-01: P0/G00 đến P9/G09 PASS theo hồ sơ và xác nhận người dùng; cold TCP/QUIC, metrics/CSV, topology và receiver IFB đã chạy thật. G08 rerun exit0/cleanup0 với tám successful evidence trials; [Evidence P8](docs/evidence/p8/README.md) giữ log/artifact review. P9 actual user rerun tại results/p9-g09-8dFdkj đủ main240+16 và controlled interrupt/cleanup; interactive terminal Ctrl+C qua tee còn issue141/cleanup1 riêng. P10/G10 đã actual PASS. P11 observability/evidence và bugfix regressions PASS; latest actual gate FAIL, patched rerun cần sudo; D28 early-keylog export đã verified, fresh packet/HOL pending.

## Bạn cần làm gì?

1. Môi trường hiện hành từ 2026-09-30: **Ubuntu dưới WSL2 trên Windows 11**. Windows VS Code là UI, mở bằng Remote WSL với workspace `WSL: Ubuntu`; terminal/build/test/network chạy trong Ubuntu WSL2. Repo phải nằm trên filesystem Linux native, ưu tiên `/home/<user>/...`, không `/mnt/c/...` hoặc `/mnt/d/...`.
2. Cho phép rõ ràng từng phase/milestone. Mặc định HUMAN-GATED: agent chỉ làm phase được phép, chạy gate, cập nhật TASK rồi dừng review; build thành công riêng lẻ không đủ. Chỉ tự tiếp tục nhiều phase khi người dùng yêu cầu rõ ràng. Khi quyền/OS chặn, agent ghi BLOCKED/lệnh thủ công và hoàn tất phần độc lập trong phase được phép. Người dùng đã cho phép riêng P11/G11; không tự mở P12.

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

## P9/G09 — actual PASS / evidence lịch sử

[P9 runbook/evidence](docs/evidence/p9/README.md) ghi behavior, files, software verification, limitation và full manual G09 command. Sau build/deps/certs bằng user và topology/server absent, chạy `sudo bash tests/system/run.sh --gate G09` trong terminal Ubuntu WSL2; capture exit/log như README. Không dùng localhost hoặc schedule256 chưa chạy thay main performance cohort. Runner tự managed server/process cleanup, giữ failures và source shards; review AB/BA/seed reset, missing-row denominator, watcher/signals/UID, network before-after và stats p95/sample stddev.

## P10/G10 — actual PASS

`make benchmark-handshake` chạy QUIC cold/resumed/early trên 1×1024 bytes/rtt50-loss0: 90 measured +6 target warmups; 64 prior ticket warm-ups lưu riêng. Cache cold rỗng; resumed/early đợi ticket notification, prior và target có t0 riêng, giữ server process. Rejection replay tối đa một lần, giữ t0 target/attempt history, final bytes/hash không đếm đôi. Stats/plots tách mode và báo transfer failures, mode achievement và fallback.

Actual user-run `results/p10-g10-cR1oR9` và archived audit PASS tại [P10 evidence](docs/evidence/p10/README.md); không cần rerun G10 hiện tại. API qualification không thay packet proof. P11 implementation/software PASS; latest actual G11 FAIL sau5 transfers. D27 sửa lifecycle/environment/capture, D28 early key export đã verified, fresh actual rerun cần sudo; xem [P11](docs/evidence/p11/README.md). Tiếp tục P11 theo user authorization, không P12.
