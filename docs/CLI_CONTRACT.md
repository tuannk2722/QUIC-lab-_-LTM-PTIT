# CLI và Make contract

Các lệnh dưới đây là **đầu ra agent phải implement**, chưa chạy được trong bộ handoff ban đầu. Defaults phải dùng chung config loader. Không dùng command string eval từ input; subprocess dùng argument list.

## 1. Binaries

`bin/server`, `bin/client`, `bin/bench`; build từ `cmd/server`, `cmd/client`, `cmd/bench`. `--help` và `--version` trên cả ba. Version in commit/build/Go/quic-go; logs stderr, machine result stdout khi dùng `--format=json`.

| Binary | Flags cốt lõi | Semantics |
|---|---|---|
| server | `--listen=0.0.0.0:4433 --transport=both --profile=bulk --profiles=configs/workloads.json` | tcp/quic/both; store theo profile |
| server | `--cert=certs/server.crt --key=certs/server.key --allow-0rtt=true` | QUIC early listener, TCP vẫn full TLS1.3 |
| server | `--ready-file=PATH --qlog-dir=PATH --keylog=PATH` | ready file atomic sau cả listeners; trace flags mặc định rỗng |
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

## 2. Exit codes và output

- 0: thao tác yêu cầu thành công; client full data + hash pass. Early demo yêu cầu “prove accepted early” thêm gate riêng, không coi fallback success là proof.
- 1: runtime/transfer/checksum/result write failure, hoặc benchmark có trial failed (vẫn hoàn thành những entry còn lại nếu testbed còn hợp lệ).
- 2: input/config/protocol setup không hợp lệ.
- 3: environment/capability/preflight bị chặn hoặc không đạt.
- Signal interrupt: 130 (INT), 143 (TERM) ở wrapper khi phù hợp; trap giữ nguyên status.

Server in readiness, endpoints và workload; client in transport/mode, scenario thực/không xác minh, bytes, timings, resource table, checksum, used0rtt và output directory. Không log secrets. Khi early rejected phải hiện rõ rejected + fallback_count, không in “0-RTT successful” chỉ vì tải thành công.

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
