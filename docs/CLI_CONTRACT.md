# CLI và Make contract

Các lệnh dưới đây là **hợp đồng cuối cùng**. P0 đã có help/version, parse/validate flags/config, build/test/certs/doctor. P2 có TCP/TLS một resource với `--profile=handshake`; P3 có bulk multiplex 6 resource với `--profile=bulk`; P4 hỗ trợ cold batch qua TCP/TLS hoặc raw QUIC. P5/P6 đã thêm metrics client và canonical raw JSON/runs.csv/streams.csv cho mỗi cold client trial. `bin/bench`, client resumed/early, plan/merge/benchmark vẫn chưa triển khai và phải trả nonzero. Defaults phải dùng chung config loader. Không dùng command string eval từ input; subprocess dùng argument list.

## 1. Binaries

`bin/server`, `bin/client`, `bin/bench`; build từ `cmd/server`, `cmd/client`, `cmd/bench`. `--help` và `--version` trên cả ba. Version in commit/build/Go/quic-go; logs stderr, machine result stdout khi dùng `--format=json`.

| Binary | Flags cốt lõi | Semantics |
|---|---|---|
| server | `--listen=0.0.0.0:4433 --transport=both --profile=bulk --profiles=configs/workloads.json` | tcp/quic/both; store theo profile |
| server | `--cert=certs/server.crt --key=certs/server.key --allow-0rtt=true` | QUIC early listener thuộc P10; P4 chỉ cold, TCP vẫn full TLS1.3 |
| server | `--ready-file=PATH --qlog-dir=PATH --keylog=PATH` | ready file atomic sau listeners được chọn; qlog/keylog thuộc P11 |
| client | `--addr=10.10.0.2:4433 --transport=tcp --mode=cold --profile=bulk` | transport tcp/quic; mode cold/resumed/early, early chỉ QUIC |
| client | `--ca=certs/server.crt --server-name=10.10.0.2 --timeout=60s` | trust đúng cert và identity |
| client | `--experiment-id=ID --run-id=ID --out=DIR --format=table` | ID tự sinh nếu thiếu; table/json; raw result ghi atomically |
| client | `--qlog-dir=PATH --keylog=PATH --progress` | Tự label evidence mode khi bật |
| client | `--mode=early --profile=handshake` | warm-up lấy ticket rồi measured attempt cùng process |
| bench | `--scenario=rtt50-loss3 --runs=30 --warmups=2 --profile=bulk --out=DIR` | Local scheduling correctness, không tự apply netem |
| bench | `--schedule-entry=PATH --out=DIR --network-state=PATH` | Đường main wrapper: chạy entry với metadata thực, output shard |
| bench | `--merge=DIR` | Đọc schedule+shards, tạo runs/streams, failed rows cho entry thiếu |
| bench | `--plan --suite=bulk --seed=SEED --out=DIR` | Xuất schedule immutable, chưa chạy network/trials |

Các flags môi trường dùng chung (addr/ca/profile/timeout) của client phải dùng được ở bench. `--mode=resumed` tạo prior connection + ticket rồi Dial thường, không gửi early. `--mode=cold` fresh cache. Bench direct không có network-state chỉ được label loopback-test/exploratory, không tự gán configured loss thành applied loss.

Schedule entry tối thiểu: schema_version, experiment_id, run_id, scenario, phase, repeat_index, pair_id, order_index, transport, mode, workload_profile, netem_seed, trace_mode. File schedule không chứa lệnh shell. Validate count/enums/paths trước thực thi. Một codepath internal run trial dùng cho cả CLI và bench.

### Hiện trạng P4/G04

`bin/server --transport=both --listen=HOST:PORT` bind TCP và UDP cùng số port trước khi in readiness hoặc tạo `--ready-file`. Một process dùng chung certificate và RAM workload store. Ready file được công bố atomically trong cùng thư mục, từ chối ghi đè marker có sẵn và xóa khi server dừng bình thường. `--transport=tcp` hoặc `quic` chỉ mở listener tương ứng. Giới hạn 8 connections đang xử lý được chia sẻ giữa hai listeners.

`bin/client --mode=cold --transport=quic` dùng một QUIC v1 connection, một bidirectional stream/resource và cùng QB01; `--transport=tcp` giữ một TLS connection và scheduler round-robin. Client QUIC gửi các REQUEST mà không chờ response của resource trước; mỗi stream gửi request rồi đóng send-half. Output JSON trên stdout vẫn có `resource_id`, `transport_stream_id` thực cho QUIC, `bytes`, `checksum_ok`, `elapsed_ms`, thêm object `metrics` P5; TCP bỏ `transport_stream_id`. Với profile bulk, 6 resource nằm trong mảng `resources`. Canonical typed record/CSV P6 nằm trong thư mục kết quả mới; stdout localhost chỉ là correctness output.

QUIC P4 cho phép server nhận 64 incoming bidirectional streams, còn client từ chối stream do server tự mở; hai phía tắt incoming unidirectional streams. Receive credits ban đầu/tối đa: 512 KiB/2 MiB mỗi stream và 2 MiB/16 MiB mỗi connection; đây là flow-control credits của quic-go, không phải kích thước resource buffer. `--allow-0rtt` vẫn là flag cho P10 và chưa kích hoạt early path; client `--mode=resumed|early` và `bin/bench` trả exit 1 / not implemented. `--qlog-dir`, `--keylog`, `--progress`, network topology/benchmark thuộc phase sau.

### Hiện trạng P5/P6

Cold client tính các mốc client monotonic theo METRICS: first DATA byte khi Read trả n>0, total_ms đến FIN cuối, elapsed_ms đến kết thúc trial và goodput chỉ khi success. Không ép request_end trước first_byte. TCP dial thành công vẫn ghi tcp_connect_ms khi TLS handshake fail; các mốc chưa có là null/ô CSV rỗng. Chưa có 0-RTT actual state nên tls_resumed/used_0rtt/early_rejected nullable, attempted_0rtt=false cho cold.

Mỗi invocation client tạo thư mục mới `results/<experiment_id>/` hoặc `--out=DIR`; ID tự sinh khi thiếu, ID chỉ gồm 1..128 ASCII chữ/số/`_`/`-`. Trong đó có `raw/<run_id>.json`, `runs.csv`, `streams.csv`; validator: `python3 analysis/validate.py DIR`. Failure sau khi trial bắt đầu vẫn ghi run và N resource rows trước khi trả exit 1. Directory đã tồn tại bị từ chối để không append/overwrite. Result write failure trả exit 1; raw đã ghi giữ lại nếu lỗi CSV và file `INCOMPLETE` còn hiện diện cho đến khi ghi đủ. Metadata network chưa được verify bởi P7/P8 được label `loopback-test` cho correctness/exploratory, không dùng làm benchmark. Full manifest và schedule/merge thuộc P9.

## 2. Exit codes và output

- 0: thao tác yêu cầu thành công; client full data + hash pass. Early demo yêu cầu “prove accepted early” thêm gate riêng, không coi fallback success là proof.
- 1: runtime/transfer/checksum/result write failure, hoặc benchmark có trial failed (vẫn hoàn thành những entry còn lại nếu testbed còn hợp lệ).
- 2: input/config/protocol setup không hợp lệ.
- 3: environment/capability/preflight bị chặn hoặc không đạt.
- Signal interrupt: 130 (INT), 143 (TERM) ở wrapper khi phù hợp; trap giữ nguyên status.

Server in readiness, endpoints và workload; client in transport/mode, scenario thực/không xác minh, bytes, timings, resource table, checksum, used0rtt và output directory. Không log secrets. Khi early rejected phải hiện rõ rejected + fallback_count, không in “0-RTT successful” chỉ vì tải thành công.

P4 hiện in readiness và kết quả transfer tối thiểu theo phần trên; các trường timing đầy đủ, `used0rtt`, scenario được xác minh và output directory là hợp đồng cho các phase metrics/results/0-RTT sau.

Bench summary có attempted/success/failed; có failures thì CSV vẫn giữ đầy đủ. Infra failure như netem apply sai → dừng cohort, không tiếp tục dưới điều kiện mạng giả.

## 3. Make targets công khai

| Target | Trách nhiệm / hoàn tất |
|---|---|
| `make doctor` | Preflight version/capability; in issue cụ thể và file report |
| `make build` | Build 3 binaries, không tự chạy benchmark |
| `make test` | Unit + integration không root |
| `make test-race` | Race tests phần app/concurrency được hỗ trợ |
| `make certs` | Local certificate SAN đúng; không overwrite key đang dùng trừ explicit flag |
| `make setup-network` | Tạo namespace/veth/IFB và ownership, idempotent |
| `make server` | Run foreground trong qserver, UID thường; Ctrl+C shutdown |
| `make demo-quic-basic` | Wrapper tự start/stop server nếu chưa có server do lab quản lý; capture evidence A |
| `make demo-baseline` | Một TCP + một QUIC bulk no-loss có verify mạng |
| `make demo-loss` | Một paired bulk rtt50-loss3 evidence; in bảng và lưu trace |
| `make demo-0rtt` | Handshake profile; warm-up/cold/resumed/early, show proof status |
| `make capture` | Capture lab port4433 theo timeout/managed PID; không chờ vô hạn |
| `make benchmark` | Main 240 measured +16 warm-up, ingress-ifb, performance mode |
| `make benchmark-handshake` | QUIC 3 modes ×30 measured; ticket warm-ups riêng |
| `make analyze RESULTS=...` | Validate → summary/charts/report, không sửa raw |
| `make clear-netem` | Gỡ impairment trong lab; giữ namespace |
| `make clean-network` | Stop owned processes rồi teardown tài nguyên lab |

`SCENARIO`, `RUNS`, `RESULTS`, `PROFILE` nếu hỗ trợ phải document/validate, không eval. Không target `clean` xóa source hoặc raw results. Live wrappers hoàn thành phải clear-netem, nhưng giữ artifacts. Nếu server foreground do người dùng chạy với profile khác, wrapper báo conflict hoặc hướng dẫn stop; không kill không rõ ownership.

## 4. Usage flow sau implementation

```bash
make doctor
make build
make test
make certs
make setup-network
make demo-quic-basic
make demo-baseline
make demo-loss
make demo-0rtt
make benchmark
make benchmark-handshake
make analyze RESULTS=results/<experiment-id>
make clean-network
```

Góc nhìn ngày demo chỉ cần demo-*; build/tests và full benchmark thực hiện trước buổi trình bày. Không cài dependency/download module trong live demo.

## 5. Bổ sung P0 — giới hạn cấu hình và preflight

Config JSON tối đa 1 MiB, độ sâu 32; từ chối unknown/duplicate keys, trailing JSON, version/generator/checksum không hỗ trợ và giá trị vượt DEMO_SPEC. Timeouts 1..3600 giây; CLI --timeout >0 và <=1h. Scenario config giới hạn repeats 1..100000, warmups 0..100000, queue 1..1000000 packets, delay 0..3600000 ms, loss 0..100%, rate >0 và <=1000000 Mbit/s, MTU1500 và main profile ingress-ifb. Đây là input bounds, không thay giá trị benchmark chính trong configs.

Bench thêm `--scenarios=configs/scenarios.json`; --plan/--schedule-entry/--merge loại trừ nhau. Chưa đọc entry/shard hay sinh schedule ở P0. Schema của entry thuộc P9; không báo input file đó đã được validate ở P0.

`make doctor REPORT=path` chỉ inventory không root; 0 chỉ nghĩa inventory đủ, không xác nhận probe đặc quyền. Script trả 3 nếu thiếu tool/môi trường hoặc không ghi được report (Make có thể trả 2 khi recipe lỗi). `sudo bash scripts/preflight-network.sh` là probe P0 độc lập, chỉ tạo/xóa tài nguyên tạm của nó; lỗi capability trả 3, signals 130/143. Không gọi sudo từ Go và không coi primitive probe là G07/G08.
