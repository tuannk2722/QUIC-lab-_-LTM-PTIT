# Báo cáo thực nghiệm — mẫu chưa có benchmark

Trạng thái tại P6/G06: **chưa có bộ đo network/benchmark**. Các file `docs/evidence/p6/` và `results/p6-g06-*` chỉ kiểm tính đúng của JSON/CSV và transfer localhost; không dùng để so sánh hiệu năng TCP/QUIC.

## Khi hoàn thành P7–P12, điền từ dữ liệu thật

1. Environment/manifest: host, WSL2, Linux/kernel, CPU/RAM/swap, Go/quic-go, TLS/CC, qdisc/IFB/offload, network placement và giới hạn.
2. Workload và phương pháp: 6×1 MiB, chunk 16 KiB; scenario, RTT/loss/rate đã kiểm; order/seed, 30 measured + 2 warmup mỗi transport/scenario; performance/evidence tách riêng.
3. Kết quả: dẫn path `runs.csv`, `streams.csv`, `summary.csv`, plots và validator output. Nêu attempted/success/failed cho mỗi cohort; mean/median/p95/sample stddev chỉ trên successful measured trials.
4. Demo: UDP/QUIC, multiplex dưới loss, cold/resumed/early với Used0RTT và trace corroboration. Mỗi hình/trace có run_id thật; kết luận HOL chỉ khi evidence đủ.
5. Hạn chế: khác biệt TCP kernel và quic-go userspace, WSL2 shared host/kernel, packetization/scheduler, seed không đồng nghĩa loss trace giống nhau, cohort nhỏ và mọi gate chưa đạt.
6. Lệnh tái lập và nguồn: tham chiếu README, manifest và `docs/REFERENCES.md`; khai báo đóng góp AI tại `docs/AI_USAGE.md`.

Không nhập số từ ví dụ minh họa vào bảng kết quả. P9/P12 sẽ điền các mục trên sau khi có dataset thật.
