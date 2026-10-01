# Báo cáo thực nghiệm — P9 actual dataset / G09 PASS

Trạng thái hiện hành 2026-10-01: P0–P8 PASS; P9 runner/manifest/cohort/stats/plots và software checks PASS, **G09 actual user rerun PASS** tại results/p9-g09-8dFdkj: main240 measured+16 warmup/256 success/1536 resources, controlled interrupt130 và cleanup0. Agent audit/hash ở evidence/p9/g09-rerun-review.json. Interactive terminal Ctrl+C qua tee từng exit141/cleanup1 còn limitation riêng. [P9 runbook/evidence](evidence/p9/README.md) có full command, actual software results và giới hạn. P10–P12 chưa mở.

`results/p9-software-6011935o/` và [bản lưu](evidence/p9/actual/) chỉ localhost correctness: 6 successful trial, 2 TLS failures và partial plan4 rows (1 success/1 actual process killed missing/2 not-started). Canonical CSV, summaries và plots được sinh từ các records này để kiểm runner/data/statistics, không dùng đánh giá hiệu năng TCP/QUIC. G08 evidence cũng không thay main cohort.

Actual main report/summary/resource-summary/plots tại `results/p9-g09-8dFdkj/main/` đã được sinh và agent tính lại từ CSV, kèm attempted/success/failed và warmup exclusion. `make analyze RESULTS=...` tái lập derived artifacts, giữ raw; `python3 tests/system/check_g09.py DIR` đối chiếu full gate. Không nhập số liệu minh họa hoặc kết luận HOL từ completion chart.

## Khi hoàn thành P7–P12, điền từ dữ liệu thật

1. Environment/manifest: host, WSL2, Linux/kernel, CPU/RAM/swap, Go/quic-go, TLS/CC, qdisc/IFB/offload, network placement và giới hạn.
2. Workload và phương pháp: 6×1 MiB, chunk 16 KiB; scenario, RTT/loss/rate đã kiểm; order/seed, 30 measured + 2 warmup mỗi transport/scenario; performance/evidence tách riêng.
3. Kết quả: dẫn path `runs.csv`, `streams.csv`, `summary.csv`, plots và validator output. Nêu attempted/success/failed cho mỗi cohort; mean/median/p95/sample stddev chỉ trên successful measured trials.
4. Demo: UDP/QUIC, multiplex dưới loss, cold/resumed/early với Used0RTT và trace corroboration. Mỗi hình/trace có run_id thật; kết luận HOL chỉ khi evidence đủ.
5. Hạn chế: khác biệt TCP kernel và quic-go userspace, WSL2 shared host/kernel, packetization/scheduler, seed không đồng nghĩa loss trace giống nhau, cohort nhỏ và mọi gate chưa đạt.
6. Lệnh tái lập và nguồn: tham chiếu README, manifest và `docs/REFERENCES.md`; khai báo đóng góp AI tại `docs/AI_USAGE.md`.

Không nhập số từ ví dụ minh họa vào bảng kết quả. P9 dataset thật đã có; report tổng hợp resumption/HOL/rehearsal vẫn chờ phase được cho phép.

Median total completion từ 30 measured trials mỗi nhóm:

| Scenario | TCP (s) | QUIC (s) |
|---|---:|---:|
| baseline | 2.649 | 2.655 |
| rtt50-loss0 | 2.971 | 2.812 |
| rtt50-loss1 | 18.312 | 12.354 |
| rtt50-loss3 | 40.899 | 24.762 |

Chỉ mô tả workload/testbed này; TCP kernel CUBIC và quic-go Reno/scheduling khác nhau. Chưa chứng minh nguyên nhân HOL. Full source CSV, p95/stddev/goodput và plots có trong main/report.md; bản lưu mọi artifacts ~4MiB ở evidence/p9/g09-user-run-artifacts.tar.gz, SHA và3695 file hashes ở review JSON.
