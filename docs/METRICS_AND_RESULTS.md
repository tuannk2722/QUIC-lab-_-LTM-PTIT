# Metrics, dữ liệu và phân tích

## 1. Đồng hồ và điểm đo

Tất cả mốc chính được tạo trong **cùng client process** bằng `time.Now()` giữ monotonic component; tính `Sub`/`Since` trước serialize. UTC RFC3339Nano dùng nhận diện run, không trừ các wall clocks để lấy latency. Việc goroutine quan sát channel có scheduling delay phải được nêu rõ.

| Mốc | Ý nghĩa chính xác |
|---|---|
| t0 | Ngay trước TCP Dial hoặc QUIC Dial/DialEarly; data/buffer/cert đã chuẩn bị |
| tTCP | TCP Dial trả thành công, trước gọi TLS HandshakeContext |
| tEarlyReady | DialEarly trả về; không đồng nghĩa handshake xong |
| tHandshake | Client quan sát secure handshake hoàn tất; failure không ghi mốc giả |
| tReqStart[i] | Trước gọi writeAll REQUEST của resource i |
| tReqEnd[i] | writeAll REQUEST trả thành công; API đã nhận bytes, không phải packet đã ra NIC |
| tFirst[i] | Read đầu tiên trả n>0 của DATA payload resource i; không tính META/header |
| tPayloadDone[i] | Đã nhận đủ DATA payload bytes |
| tDone[i] | Parser nhận FIN hợp lệ và đã đủ size |
| tAll | max(tDone[i]) của mọi resource |
| tEnd | Trial success hoàn tất timing hoặc phát hiện failure/cancel; chưa tính xuất file |

Handshake observer phải được bắt đầu ngay khi API cho phép; không cố backdate nếu quan sát muộn. Khi early bị reject, giữ t0 gốc xuyên qua retry; separate attempt events ghi retry start/request. Không reset t0 để fallback trông nhanh hơn.

## 2. Công thức

| Field | Công thức / đơn vị |
|---|---|
| tcp_connect_ms | (tTCP−t0), chỉ TCP |
| handshake_ms | (tHandshake−t0), secure setup tổng, TCP gồm TCP handshake |
| tls_handshake_ms | (tHandshake−tTCP), chỉ TCP |
| connect_ms | Bằng handshake_ms; compatibility alias, không dùng early-ready |
| early_ready_ms | (tEarlyReady−t0), chỉ early-mode |
| request_start_ms / request_end_ms | tReqStart/End[i]−t0 |
| first_byte_ms | tFirst[i]−t0; cold-start first byte từng resource |
| ttfb_request_ms | tFirst[i]−tReqStart[i]; gồm thời gian Write/request và server batch wait |
| payload_done_ms / complete_ms | tPayloadDone/tDone[i]−t0 |
| completion_request_ms | tDone[i]−tReqStart[i] |
| ttfa_ms | min(tFirst[i])−t0, byte resource đầu tiên toàn trial |
| transfer_ms | tAll−min(tReqStart[i]) |
| total_ms | tAll−t0; chỉ complete trial có đủ FIN |
| elapsed_ms | tEnd−t0; có cả failure/timeout |
| goodput_mbps | 8 × tổng resource payload bytes / (transfer_ms × 1000) |
| e2e_goodput_mbps | 8 × tổng resource payload bytes / (total_ms × 1000) |

Goodput dùng payload hữu ích, không cộng header/META, retransmissions, bytes bị lặp hoặc TLS/QUIC overhead. Mbps là 10^6 bit/s; MiB là 2^20 bytes. Không gọi goodput là wire throughput. Khi duration<=0 hoặc trial fail, goodput để null, không chia 0 hoặc đẩy lên vô cực.

tReqEnd có thể sau tFirst do scheduling/buffering; không tạo assert sai `first >= request_end`. Với cold yêu cầu request bắt đầu sau secure readiness, với early cho phép trước observed handshake. Hash tất cả resource **sau** tAll để CPU hashing không làm chậm resource khác còn đang nhận.

## 3. Bố cục kết quả

Mỗi invocation có thư mục mới `results/<experiment_id>/`; không append vào kết quả cũ một cách không kiểm soát. `experiment_id` gồm timestamp + random suffix; run_id duy nhất trong toàn experiment. Hai mode `performance` và `evidence` không gộp.

| Artifact | Nội dung |
|---|---|
| manifest.json | Toolchain/OS/VM/config/hash/seed/trace mode/commit/CLI và giới hạn |
| runs.csv | Một dòng/mỗi trial, kể cả warm-up và failed |
| streams.csv | N dòng/trial, kể cả tài nguyên chưa được request/không hoàn tất |
| raw/<run_id>.json | Bản ghi typed canonical trước flatten CSV |
| attempts/<run_id>.json | Optional: 0-RTT early/rejection/fallback events với attempt ID |
| progress.csv | Chỉ evidence: tiến độ payload tích lũy của từng resource |
| qlog/, pcap/, keylog/ | Chỉ evidence, mapping cụ thể ở manifest |
| network/ | Trạng thái thực tế, qdisc counters trước/sau và offload/config |
| summary.csv, plots/, report.md | Sinh từ CSV thật; không sửa raw input |

Client và server qlog có connection ID, perspective và run mapping. Một server phục vụ nhiều run phải map connection qua endpoint/time/correlation file đã kiểm tra, không suy ra filename thứ tự. TLS key log chỉ local cho demo, gitignore, không commit mặc định.

## 4. CSV contract v1

UTF-8, comma, header cố định, quoting chuẩn CSV, decimal dấu chấm, boolean `true/false`, null là ô rỗng (không phải 0). Không ghi nan/inf. Version mọi row=`1`. Không ghi đồng thời từ nhiều goroutines; aggregator/writer duy nhất. CSV và canonical JSON phải nhất quán.

`runs.csv`, thứ tự:

```csv
schema_version,experiment_id,run_id,phase,repeat_index,pair_id,order_index,timestamp_utc,scenario,transport,mode,trace_mode,network_profile,resource_count,resource_size_bytes,chunk_bytes,delay_each_way_ms,loss_downstream_pct,loss_upstream_pct,rate_mbps,netem_seed,bytes_expected,bytes_received,tcp_connect_ms,tls_handshake_ms,handshake_ms,connect_ms,early_ready_ms,ttfa_ms,transfer_ms,total_ms,elapsed_ms,goodput_mbps,e2e_goodput_mbps,tls_resumed,attempted_0rtt,used_0rtt,early_rejected,fallback_count,success,error_code,error_message
```

Enums: phase=`warmup|measured|evidence`; transport=`tcp|quic`; mode=`cold|resumed|early`; trace_mode=`performance|evidence`; network_profile=`ingress-ifb|egress-demo|loopback-test`. `pair_id` nối 2 transport cùng repeat; order_index là vị trí chạy trong pair. 0-RTT comparisons pair/group ghi manifest; không gán TCP early mode.

`error_code` là mã ổn định cấp ứng dụng (ví dụ timeout, checksum_mismatch, protocol_error, environment_error), không giới hạn ở số ERROR của QB01; raw JSON có thể lưu cause/wire code trong diagnostics. `error_message` ngắn, không chứa secrets. `attempt_index` bắt đầu 0, fallback sau rejected là 1; fallback_count là số lần replay batch.

`bytes_received`: bytes resource được nhận hợp lệ của attempt cuối phục vụ kết quả, không đếm lại early data đã bỏ; diagnostic attempted bytes ở attempts. `fallback_count` 0 hoặc 1. `used_0rtt` là trạng thái thực tế của connection attempt; với rejected=false + fallback completion, không tự chuyển thành true. Không có handshake thành công → nullable state khi chưa xác định, attempted_0rtt vẫn true nếu đã gọi early API với ý định thử. `success` chỉ true khi tất cả FIN/size/hash đúng và cleanup không phát hiện protocol error.

`streams.csv`, thứ tự:

```csv
schema_version,experiment_id,run_id,resource_id,transport_stream_id,attempt_index,request_start_ms,request_end_ms,first_byte_ms,ttfb_request_ms,payload_done_ms,complete_ms,completion_request_ms,bytes_expected,bytes_received,checksum_ok,success,error_code,error_message
```

TCP transport_stream_id rỗng; QUIC ghi ID thực của attempt cuối. Resource chưa mở stream có các mốc rỗng. Khi rejected, N final rows phản ánh successful fallback hoặc failure; history không bị xóa, giữ attempts file. Không trộn milestones của stream cũ với stream mới.

`progress.csv`:

```csv
schema_version,experiment_id,run_id,resource_id,attempt_index,elapsed_ms,payload_bytes_received
```

Evidence mode ghi khi vượt mốc 16KiB hoặc chunk cuối, append in-memory events rồi flush sau timing. Progress 1KiB profile ít điểm là bình thường. Không ghi terminal mỗi byte/read.

## 5. Manifest bắt buộc

OS/kernel, VM hypervisor nếu xác định được, vCPU/RAM, Go/quic-go version, build flags, git commit hoặc `uncommitted`, dirty flag, ngày UTC, CLI, workload checksum/generator version, TLS/ALPN/version/cipher, TCP CC từ kernel, QUIC CC/default có bằng chứng phiên bản, QUIC flow-control/stream limits, MTU, socket buffer settings, offload state, network placement và qdisc/filter output, configured/measured RTT, seeds, timeout, trace state, config/schema hash, runner order và failure policy.

Không biết field nào ghi `unknown` kèm lý do, không bịa “CUBIC giống nhau” khi chưa xác minh. Hai CC cùng tên vẫn khác implementation. Manifest phản ánh cấu hình thực, không chỉ copy desired JSON.

## 6. Thống kê và biểu đồ

- Bulk: 4 scenario chính × 2 transport × 30 measured = **240 trial đo**. Warm-up thêm 2 mỗi transport/scenario = 16, lưu phase riêng.
- Chạy tuần tự, AB/BA balanced theo seed. TCP/QUIC không cùng tranh một bottleneck ở cùng thời điểm.
- Summary theo scenario, transport, mode, profile, trace mode; `n_attempted`, `n_success`, `n_failed`, failure_rate luôn đi cùng mean/median/p95/sample_stddev.
- Successful latency aggregate chỉ tính success=true, đồng thời hiển thị failure count/timeouts. Không thay failed duration bằng 0; không xóa outliers vì “xấu”. Ghi lý do loại run do testbed lỗi, giữ raw và rerun cohort nếu cần.
- p95 nearest-rank: sort n giá trị tăng, index `ceil(.95*n)-1`. Sample stddev mẫu n−1; n<2 → null. Median chẵn trung bình hai phần tử giữa. Không gộp 6 resource correlated trong cùng run thành 6 independent trials.
- Required plots: total_ms và ttfa_ms theo scenario/transport (box/points); goodput theo scenario; per-resource completion distribution; evidence progress timeline. Trục/units/n/failures hiển thị. 0-RTT plot nhóm cold/resumed/early riêng bằng handshake workload.
- Chart HOL phải kèm run_id và lời giải thích evidence; không dùng bar completion để tuyên bố stream cụ thể là stream duy nhất mất packet. Qlog có thể cho thấy packet chứa nhiều streams.

## 7. Kiểm tra dữ liệu

Schemas trong `schemas/` định nghĩa header/field type, enums, nullability; chưa có result rows. Agent implement validation: unique run_id, streams FK, N rows/trial, metrics đúng công thức với tolerance floating, totals không âm, success yêu cầu bytes/hash đúng, main cohorts đúng count/config, không trộn trace mode. JSON schema định nghĩa record; validator CSV chuyển kiểu theo mapping rồi validate.

CSV write failure làm command nonzero; raw output đã ghi giữ lại với trạng thái incomplete. Writer flush/close error phải được kiểm. Timeout process phải tạo failed row từ runner, không im lặng thiếu run.
