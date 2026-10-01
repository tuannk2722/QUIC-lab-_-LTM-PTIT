# CLI và Make contract

Các lệnh dưới đây là **hợp đồng cuối cùng**. P0–P8/G00–G08 đã PASS, gồm cold TCP/QUIC, canonical metrics/results và receiver IFB thực. P9 có bulk bench plan/entry/merge, orchestrator, manifest và CSV-derived stats/plots; software checks và full G09 actual user rerun PASS; main240+16/1536 rows, controlled SIGINT/cleanup verified. Interactive terminal Ctrl+C qua tee từng exit141/cleanup1 vẫn là limitation riêng. Client resumed/early và handshake suite còn thuộc P10; traces thuộc P11. Defaults dùng chung config loader. Không dùng command string eval từ input; subprocess dùng argument list.

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
| client | `--network-state=PATH` | Snapshot inspect.sh mới trong 5 phút, đúng qclient identity; gắn scenario/profile/rate/loss/seed, phase/trace_mode=evidence trong P8 |
| client | `--qlog-dir=PATH --keylog=PATH --progress` | Tự label evidence mode khi bật |
| client | `--mode=early --profile=handshake` | warm-up lấy ticket rồi measured attempt cùng process |
| bench | `--scenario=rtt50-loss3 --runs=30 --warmups=2 --profile=bulk --out=DIR` | Local scheduling correctness, không tự apply netem |
| bench | `--schedule-entry=PATH --out=DIR --network-state=PATH` | Đường main wrapper: chạy entry với metadata thực, output shard |
| bench | `--merge=DIR` | Đọc schedule+shards, tạo runs/streams, failed rows cho entry thiếu |
| bench | `--plan --suite=bulk --seed=SEED --out=DIR` | Xuất schedule immutable, chưa chạy network/trials |
| bench | `--plan --network-profile=ingress-ifb\|loopback-test --disable-netem-seed` | Main hoặc correctness plan; seed=null chỉ khi chọn explicit limitation |

Các flags môi trường dùng chung (addr/ca/profile/timeout) của client phải dùng được ở bench. `--mode=resumed` tạo prior connection + ticket rồi Dial thường, không gửi early. `--mode=cold` fresh cache. Bench direct không có network-state chỉ được label loopback-test/exploratory, không tự gán configured loss thành applied loss.

Schedule entry tối thiểu: schema_version, experiment_id, run_id, scenario, phase, repeat_index, pair_id, order_index, transport, mode, workload_profile, netem_seed, trace_mode. File schedule không chứa lệnh shell. Validate count/enums/paths trước thực thi. Một codepath internal run trial dùng cho cả CLI và bench.

### Hiện trạng P4/G04

`bin/server --transport=both --listen=HOST:PORT` bind TCP và UDP cùng số port trước khi in readiness hoặc tạo `--ready-file`. Một process dùng chung certificate và RAM workload store. Ready file được công bố atomically trong cùng thư mục, từ chối ghi đè marker có sẵn và xóa khi server dừng bình thường. `--transport=tcp` hoặc `quic` chỉ mở listener tương ứng. Giới hạn 8 connections đang xử lý được chia sẻ giữa hai listeners.

`bin/client --mode=cold --transport=quic` dùng một QUIC v1 connection, một bidirectional stream/resource và cùng QB01; `--transport=tcp` giữ một TLS connection và scheduler round-robin. Client QUIC gửi các REQUEST mà không chờ response của resource trước; mỗi stream gửi request rồi đóng send-half. Output JSON trên stdout vẫn có `resource_id`, `transport_stream_id` thực cho QUIC, `bytes`, `checksum_ok`, `elapsed_ms`, thêm object `metrics` P5; TCP bỏ `transport_stream_id`. Với profile bulk, 6 resource nằm trong mảng `resources`. Canonical typed record/CSV P6 nằm trong thư mục kết quả mới; stdout localhost chỉ là correctness output.

QUIC P4 cho phép server nhận 64 incoming bidirectional streams, còn client từ chối stream do server tự mở; hai phía tắt incoming unidirectional streams. Receive credits ban đầu/tối đa: 512 KiB/2 MiB mỗi stream và 2 MiB/16 MiB mỗi connection; đây là flow-control credits của quic-go, không phải kích thước resource buffer. `--allow-0rtt` vẫn là flag cho P10 và chưa kích hoạt early path; client `--mode=resumed|early` trả exit 1 / not implemented. `--qlog-dir`, `--keylog`, `--progress` thuộc P11; P9 performance bench từ chối bật các flags này.

### Hiện trạng P5/P6

Cold client tính các mốc client monotonic theo METRICS: first DATA byte khi Read trả n>0, total_ms đến FIN cuối, elapsed_ms đến kết thúc trial và goodput chỉ khi success. Không ép request_end trước first_byte. TCP dial thành công vẫn ghi tcp_connect_ms khi TLS handshake fail; các mốc chưa có là null/ô CSV rỗng. Chưa có 0-RTT actual state nên tls_resumed/used_0rtt/early_rejected nullable, attempted_0rtt=false cho cold.

Mỗi invocation client tạo thư mục mới `results/<experiment_id>/` hoặc `--out=DIR`; ID tự sinh khi thiếu, ID chỉ gồm 1..128 ASCII chữ/số/`_`/`-`. Trong đó có `raw/<run_id>.json`, `runs.csv`, `streams.csv`; validator: `python3 analysis/validate.py DIR`. Failure sau khi trial bắt đầu vẫn ghi run và N resource rows trước khi trả exit 1. Directory đã tồn tại bị từ chối để không append/overwrite. Result write failure trả exit 1; raw đã ghi giữ lại nếu lỗi CSV và file `INCOMPLETE` còn hiện diện cho đến khi ghi đủ. Nếu không có `--network-state`, cold CLI giữ `network_profile=loopback-test` cho correctness/exploratory. P8 flag nhận snapshot đã verify, đúng namespace và mới trong 5 phút; gắn network fields và phase/trace_mode=evidence, không đưa G08 vào main cohort. P9 bench entry nhận cùng snapshot nhưng phase warmup/measured và trace_mode=performance đến từ schedule.

### Hiện trạng P7/G07

`make setup-network` gọi setup đặc quyền để tạo topology cố định qclient/qserver, veth `eth0` MTU 1500, `lo` và `ifb0` up. Setup nạp IFB với `numifbs=0` trước namespace IFB để không sinh thiết bị mặc định trên host; G07 rerun đã PASS trong boot hiện tại (first-load sau fresh boot vẫn chưa kiểm). Marker root-owned ở `/run/quic-performance-lab/topology-v1` gắn UID/GID người gọi sudo với identity namespace; setup lặp lại được khi owned topology khớp, từ chối collision/marker sai và rollback khi setup lỗi hoặc bị INT/TERM. `scripts/run-in-netns.sh qclient|qserver -- command args...` kiểm marker/topology, vào namespace bằng root rồi chạy command dưới UID/GID người gọi sudo qua `setpriv --clear-groups`. Server/client không chạy root. `make server PROFILE=bulk` build bằng user rồi chạy foreground trong qserver trên TCP+UDP :4433; Ctrl+C dừng server. `PROFILE` được truyền thành một argument và CLI kiểm tên profile, không eval. `make clean-network` chỉ xóa tài nguyên owned sau khi namespace hết PID; nếu còn server, dừng foreground trước. P8 gắn tc ingress/netem lên IFB khi apply, không tự bật trong setup.

Từ repo root trong Ubuntu WSL2, với cert local đã có và `results/` writable:

```bash
make setup-network
make server PROFILE=bulk
# Terminal khác, sau readiness:
sudo bash scripts/run-in-netns.sh qclient -- "$PWD/bin/client" --transport=tcp --addr=10.10.0.2:4433 --server-name=10.10.0.2 --format=json
sudo bash scripts/run-in-netns.sh qclient -- "$PWD/bin/client" --transport=quic --addr=10.10.0.2:4433 --server-name=10.10.0.2 --format=json
# Sau Ctrl+C ở terminal server:
make clean-network
```

G07 đầy đủ dùng `sudo bash tests/system/run.sh` từ trạng thái qclient/qserver chưa tồn tại; runner kiểm collision, partial failure, hai vòng setup/teardown, ping, TCP/QUIC transfers, UID, SIGINT và host link/address/routes. Lần đầu user chạy dừng tại host comparison trước transfer và tạo hai IFB host; lệnh recovery có precheck snapshot tại `scripts/network/restore-host-ifb.sh`. Recovery exit 0 và rerun G07 exit 0 đã có log, bốn trial dirs và host comparisons tại evidence/p7. Build/test hoặc P0 preflight không thay system gate.

### Hiện trạng P8/G08

`sudo bash scripts/network/netem.sh --scenario=NAME [--scenarios=PATH] [--profile=ingress-ifb|egress-demo] [--seed=default|UINT64|none]`: dùng configs/scenarios.json, validate trước khi đổi mạng; xóa profile cũ, tắt offloads liên quan trên eth0/ifb0, apply và đối chiếu actual kernel JSON. Profile chính redirect exact IPv4 10.10.0.1↔10.10.0.2 sang IFB receiver; ARP bypass. Egress-demo chỉ netem trên eth0, nhãn riêng. Root-owned impairment metadata nằm trong /run/quic-performance-lab, dùng chung ownership lock P7; không giữ lock khi client chạy. Handle 1: (netem) và ffff:/pref10 (ingress flower/mirred) reserved cho lab; từ chối qdisc/filter foreign. Apply/inspect JSON ra stdout; dùng tee/redirect của user để lưu file, không mở output path tùy ý với root.

`--seed=default` lấy base_seed từ config, verify kernel/tc report. Lỗi seed không bị silently bỏ: command nonzero; `--seed=none` là lựa chọn explicit seed=null, disabled-explicitly. Bản ghi offload có before/after và requested/fixed/absent/failed; feature còn ON làm apply fail. `sudo bash scripts/network/inspect.sh` đọc actual qdisc/filter/counters/link/address/offload/CC và kiểm với metadata apply trước khi verified=true. Snapshot sau clear có verified=false, không được client dùng để gán applied network.

`client --network-state=PATH` là metadata handoff từ wrapper, không tự cấp quyền hoặc truy vấn tc; snapshot không bảo đảm kernel không đổi sau khi đọc. Wrapper phải inspect trước/sau mỗi trial và apply/reset khi idle, sau probes. P8 gắn phase/trace_mode=evidence vì đây là gate validation trials, chưa có benchmark schedule P9. Input snapshot lỗi/stale/wrong namespace exit 2 trước t0. Trial failure giữ cùng network metadata trong raw/CSV. Schema kết quả vẫn v1.

`make netem SCENARIO=rtt50-loss0 NETWORK_PROFILE=ingress-ifb NETEM_SEED=default`; `make -s inspect-network` xuất JSON sạch; `make clear-netem` gỡ qdisc/filter giữ namespaces và offload OFF; teardown xóa toàn topology và impairment metadata. Clear không restore offloads của disposable veth/IFB; không sửa host NIC. `make test-network` chạy Python negative tests UID thường. Actual G08: `sudo bash tests/system/run.sh --gate G08` (không args vẫn G07); gate cần topology ban đầu absent, server/client unprivileged, output user-owned. Test-only `QUICLAB_FAIL_NETEM_AFTER=client` cố ý gây tc parser error sau qclient apply để kiểm rollback; không dùng trong benchmark. Actual G08 rerun đã PASS; evidence/p8 giữ lịch sử và review.

### Hiện trạng P9/G09

`bench --plan` mặc định chọn mọi main scenario, counts/seed từ configs; `--scenario=NAME` chọn một scenario. Schedule v1 nhúng validated configs/hash, endpoint/CA hash/timeout và entries. SplitMix64 v1 tạo starting AB/BA order rồi alternate từng pair, balanced khi repeats chẵn; seed riêng mỗi pair, reset cùng seed trước từng transport. `--seed=0` là explicit seed hợp lệ. Schedule tối đa4096 entries/JSON8MiB, không có shell command. `entries/<run_id>.json` gắn schedule hash và exact entry; không nhận override transport/scenario/order/run ID hoặc chạy lại shard có sẵn.

`bench --schedule-entry=PATH` chạy đúng một cold trial trong qclient sau config/CA hash và snapshot/namespace checks; output mặc định `shards/<run_id>/`. Cùng RunCold codepath với client, không gọi sudo/tc. `connection.json` ghi actual TLS/ALPN/cipher/resumption, QUIC version/Used0RTT và client socket buffers trong cleanup sau FIN; không đổi schema canonical v1. Bench direct chạy TCP/QUIC tuần tự của một scenario và luôn loopback-test; configured losses không được gán là đã apply. Network-state direct bị từ chối vì reset phải qua wrapper.

`scripts/bench.sh` yêu cầu topology ban đầu absent, G08 PASS và pinned analysis packages; tạo plan bằng user, setup/RTT probes, server managed PID UID thường, reset/apply/inspect mỗi entry, watchdog timeout+15s/KILL grace5s, check after/counters/direction/rate. Transfer fail có raw hợp lệ được giữ và tiếp tục sau full server deadline/queue drain/quiet path; lỗi infra hoặc missing/incomplete output dừng cohort. Trap giữ130/143, dừng đúng PID do wrapper tạo, clear/teardown và compare host. Wrapper actual main và controlled SIGINT đã PASS ở user rerun results/p9-g09-8dFdkj; terminal Ctrl+C qua tee trước đó exit141/cleanup1, chưa sửa/kiểm lại đường tương tác này.

Merge chạy một lần, không append/overwrite aggregate. Giữ source shards; failed representation cho entry thiếu với N rows, null latency/hash và explicit code. `n_attempted` là full scheduled denominator, `n_invoked` riêng; unobserved elapsed=0 sentinel được ghi ở merge.json, không là latency đo. Raw có before/after network check thiếu/lỗi bị đánh dấu environment_error trong aggregate, source không đổi. Summary/plots chỉ successful measured latency, luôn kèm failures; warmups riêng. Full G09: `sudo bash tests/system/run.sh --gate G09`, gồm actual interrupted trial và main256 rows/1536 resource rows; software/local correctness không thay gate.

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
| `make netem` | Apply scenario/profile/seed P8, clear cũ và verify kernel |
| `make inspect-network` | Actual JSON; dùng make -s để không lẫn recipe echo |
| `make test-network` | Python negative tests P8 unprivileged; không thay G08 |
| `make analysis-deps` | Cài pinned plotting packages vào .tools/analysis bằng user, trước benchmark/live |
| `make test-analysis` | Unit formulas/failure denominator/warmup/outliers; không tạo main benchmark |
| `make clear-netem` | Gỡ qdisc/filter trong lab; giữ namespace và offload OFF |
| `make clean-network` | Stop owned processes rồi teardown tài nguyên lab |

`SCENARIO`, `RUNS`, `RESULTS`, `PROFILE` nếu hỗ trợ phải document/validate, không eval. P7 hỗ trợ `PROFILE` cho `make server`; P8 hỗ trợ `SCENARIO`, `NETWORK_PROFILE`, `NETEM_SEED` cho apply, truyền qua environment thành arguments, parser kiểm input; không eval. `NETEM_SEED=none` là explicit limitation. Không target `clean` xóa source hoặc raw results. Live wrappers hoàn thành phải clear-netem, nhưng giữ artifacts. Nếu server foreground do người dùng chạy với profile khác, wrapper báo conflict hoặc hướng dẫn stop; không kill không rõ ownership.

P9 `make benchmark` nhận optional RUNS/WARMUPS/SEED (mặc định trống, Go đọc configs); thay counts là exploratory, không G09 default. Main luôn bulk/ingress-ifb/mọi main scenario; dùng scripts/bench.sh --scenario=NAME cho subset. NETEM_SEED=none là explicit limitation, không dùng một fixed seed thay seed schedule. `make analyze RESULTS=DIR` validate → summary → plots/report, không sửa raw. Các biến thành argument arrays, không eval.

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
