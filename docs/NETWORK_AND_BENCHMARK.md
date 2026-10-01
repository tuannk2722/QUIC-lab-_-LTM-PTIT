# Môi trường mạng và thí nghiệm

## 1. Môi trường đã chọn

Môi trường chính hiện hành (D13, 2026-09-30): Ubuntu dưới WSL2 trên Windows 11. Một môi trường Ubuntu WSL2 chứa cả qclient/qserver namespace; không yêu cầu cloud server hoặc hai máy ảo. Repo phải nằm trong native WSL Linux filesystem, ưu tiên `/home/<user>/...`, không `/mnt/c/...` hoặc `/mnt/d/...`. Windows VS Code là UI qua Remote WSL (`WSL: Ubuntu`); build/test/network chạy trong Ubuntu WSL2. Ghi lại tài nguyên thực và giới hạn CPU/RAM/swap ở P0/manifest; không yêu cầu vượt máy có sẵn. Linux GUI không cần thiết.

Capability preflight do người dùng cung cấp đã PASS netns/veth/netem/IFB/mirred; tcpdump có sẵn (quan sát trong VERSIONS). Chỉ chứng minh primitives có sẵn, không thay G07/G08, packet-path/counter/RTT/rate verification hoặc benchmark methodology. Main ingress-ifb không được hạ xuống egress-demo.

P0 kiểm tra `uname`, `/etc/os-release`, `go version`, `ip -V`, `tc -V`, `make`, `openssl`, `tcpdump`, `ethtool`, Python plotting tools, namespace/capabilities, `sch_netem`, IFB và redirect. Không tự bảo đảm kernel nào cũng hỗ trợ. Thiếu capability → ghi blocked và lệnh fix phù hợp distro; không tự cài OS hoặc thay global network để né giới hạn.

## 2. Topology

| Thành phần | Namespace/interface | Địa chỉ |
|---|---|---|
| Client/bench | qclient / eth0 | 10.10.0.1/24 |
| Server | qserver / eth0 | 10.10.0.2/24 |
| Link | veth pair, mỗi đầu rename eth0 | MTU 1500 |
| Receiver shaping | ifb0 trong từng namespace | Không cần IP |
| Server listeners | TCP và UDP | :4433 |

Không default route/NAT/forward host cần thiết để traffic giữa hai endpoints; cùng subnet nối trực tiếp. Loopback trong mỗi namespace phải up. Hai namespaces chỉ cô lập network stack, vẫn chung kernel/CPU/storage của Ubuntu WSL2.

Đề xuất setup ban đầu: `ip netns add`; tạo veth-client/veth-server; move từng đầu; rename eth0; gán IP; up lo/eth0. Bản triển khai thêm ownership marker để không xóa namespace trùng tên thuộc công việc khác. Setup/teardown lặp được trên tài nguyên của lab; nếu trùng tên không có ownership hợp lệ thì báo rõ, không delete mù.

P7 dùng marker root-owned mode 0600 tại `/run/quic-performance-lab/topology-v1` trong thư mục mode 0700. Marker lưu UID/GID người gọi sudo và định danh device:inode của cả hai namespace. Setup từ chối tên `qclient`/`qserver` có sẵn mà marker không xác thực; setup lỗi/INT/TERM rollback chỉ những namespace vừa tạo và có định danh khớp. Teardown kiểm marker và định danh trước khi xóa; nếu còn PID trong namespace thì báo lỗi để người vận hành dừng process trước, không tự kill PID không rõ chủ. `ifb0` được tạo/up trong P7; ingress mirred/netem và kiểm counter thuộc P8. Việc script trả thành công chưa thay bằng chứng traffic, cleanup interrupt và host-state của G07.

Lần chạy G07 đầu tiên ngày 2026-10-01 cho thấy tạo IFB trong namespace khi driver chưa nạp kích hoạt mặc định `numifbs=2`, sinh thêm `ifb0`/`ifb1` trên host. Setup P7 sau sửa gọi `modprobe ifb numifbs=0` trước khi tạo namespace IFB và kiểm danh sách host link không đổi ngay sau nạp module. Hai IFB host từ lần lỗi cũ phải được khôi phục riêng bằng precheck snapshot trước khi chạy lại gate; không coi chúng là topology lab hoặc âm thầm xóa trong teardown. Nguồn cơ chế: [Linux kernel IFB driver](https://github.com/torvalds/linux/blob/master/drivers/net/ifb.c). G07 vẫn cần snapshot host thực trước/đang hoạt động/sau teardown ở lần rerun.

## 3. Hai profile network, không trộn kết quả

### ingress-ifb — profile benchmark chính

Ở mỗi namespace: tạo ifb0/up; ingress hook trên eth0; redirect IPv4 ingress sang ifb0 bằng tc mirred; netem ở root egress của IFB mô phỏng phía nhận.

| IFB nơi nhận | Hướng mô phỏng | Delay | Loss | Rate |
|---|---|---:|---:|---:|
| qserver/ifb0 | client → server | d ms | upstream_pct | R Mbit/s |
| qclient/ifb0 | server → client | d ms | downstream_pct | R Mbit/s |

Vì mỗi direction qua đúng một netem, configured RTT thêm ≈2d. Không để egress eth0 vẫn có delay cùng lúc gây nhân đôi RTT. Filter chỉ IPv4 lab traffic; ARP có thể bypass để ổn định neighbor resolution. Probe/ping làm trước trial; không chạy background ping trong measured transfer.

Lý do receiver placement: tài liệu iproute2/netem lưu ý TSQ ở sender có thể làm phép thử TCP không thực tế. Đây là cải tiến kỹ thuật từ bản đề xuất egress, không đổi mục tiêu/cấu trúc ứng dụng. IFB thuộc lab, wrapper cần verify packet path/counters thực sự đi qua, không chỉ `tc` exit 0.

### egress-demo — profile minh họa đơn giản

qclient eth0: delay d, loss upstream; qserver eth0: delay d, loss downstream; rate R cả hai phía. Giữ để tái hiện ví dụ ban đầu/debug. Label rõ egress-demo; **không** dùng thay ingress-ifb trong báo cáo chính mà không ghi đổi thiết kế/giới hạn. IFB không dùng trong mode này.

Cả hai profile dùng `limit 1000` packets mặc định, MTU1500; kiểm queue/drops và BDP. Delay/loss/rate/jitter/reorder là mô hình, không bản sao đầy đủ Wi-Fi/Internet. Với profile 20Mbps/50ms, BDP một RTT xấp xỉ 125,000 bytes; phải kiểm thêm burst/buffer effects thay vì giả định limit 1000 là tối ưu mọi case.

## 4. Scenarios

`configs/scenarios.json` là nguồn số liệu cấu hình, script không hardcode bản thứ hai.

| Tên | d mỗi chiều | Loss downstream | Loss upstream | Rate mỗi chiều |
|---|---:|---:|---:|---:|
| baseline | 0ms | 0% | 0% | 20Mbps |
| rtt50-loss0 | 25ms | 0% | 0% | 20Mbps |
| rtt50-loss1 | 25ms | 1% | 0% | 20Mbps |
| rtt50-loss3 | 25ms | 3% | 0% | 20Mbps |
| rtt100-loss3 (extension) | 50ms | 3% | 0% | 20Mbps |

Configured loss là probability, không đảm bảo mỗi run mất đúng phần trăm này. Loss downstream khi bật từ đầu có thể tác động handshake/control/ACK mang trên đường đó, không chỉ DATA. Không claim biết ResourceID từ encrypted packet bằng tc filter. Symmetric loss/jitter/reorder optional, cohort riêng.

netem seed được lưu nếu kernel/iproute2 hỗ trợ. Cùng seed không có nghĩa TCP và QUIC mất cùng application bytes: packetization/packet count khác. Thay seed giữa repeats; paired transport có thể cùng configured seed nhưng không gọi là identical loss trace. Nếu không hỗ trợ seed, lưu null và limitation; không giả hỗ trợ hoặc silently bỏ flag khỏi manifest.

## 5. Kiểm tra đường mạng trước đo

- Link/address/namespace đúng; readiness của cả listeners.
- Ping trong no-loss scenario: đo median ít nhất 10 mẫu, ghi configured/measured. Với rtt50-loss0, median mục tiêu 50ms ±10ms; baseline <10ms khi Ubuntu WSL2 và host rảnh. Ngoài range → không tiến hành main cohort trước khi chẩn đoán.
- Xem `tc -s`/filter redirect/IFB trước và sau traffic; counter phải tăng đúng direction; không duplicate shaping.
- Ghi `ethtool -k` và tắt những segmentation/coalescing offload có thể trên veth/IFB cho profile measurement (GSO/GRO/TSO và UDP segmentation nếu tồn tại). Lưu điều gì fixed/không hỗ trợ. Không sửa physical NIC host. Không ép tắt option không hỗ trợ rồi báo đã tắt.
- Với payload lớn, goodput gần 20Mbps hoặc thấp hơn là hợp lý; nếu cao hơn đáng kể (>10% trên sustained bulk), kiểm units/placement/offload/timer. Không coi 10% là định luật rate tuyệt đối cho trace ngắn.
- Chụp qdisc config và counters trước/sau; ghi drops, backlog, overlimits. qdisc drops tổng có thể gồm queue overflow và configured random loss; không equate tất cả với random loss.
- Warm-up neighbor cache/CPU trước đo; qdisc reset lúc server idle, sau probes để probe không tiêu thụ random sequence của measured trial khi có seed.

## 6. Tách đặc quyền và orchestrate

`scripts/network/*.sh`: quyền cần thiết để add/delete namespace/qdisc/ifb. `scripts/run-in-netns.sh`: vào namespace bằng quyền hệ thống rồi hạ về UID/GID người chạy. Lưu UID/GID trước sudo; output writable bởi user. Server/client/bench không chạy root. Không `chmod 777`, không sudo go build/download dependencies.

`scripts/bench.sh` có thể áp scenario/seed rồi gọi bench cho một paired repeat trong namespace; Go bench quản lý TCP/QUIC trials và kết quả. Tạo file order/seed schedule một lần ở orchestrator; config hash lưu cùng experiment. Mỗi pair đổi thứ tự AB/BA balanced; khi cần reset qdisc giữa hai transport, wrapper phải điều phối subtrial rõ ràng qua lệnh bench một-trial. Không để Go process quyền thường tự chạy sudo.

Một cách implement chuẩn: shell gọi `bench --plan` để tạo schedule JSON; lặp schedule entries {scenario,pair_id,order,transport,seed}; áp/verify network; gọi `bench --schedule-entry=...` unprivileged; bench thực thi một trial và ghi shard. Cuối cùng bench merge shards theo lịch thành hai CSV chính và failed rows còn thiếu. Không concurrent CSV append. CLI bên ngoài vẫn `make benchmark` một lệnh.

Cleanup bằng trap EXIT/INT/TERM, lưu exit code gốc, không che failure bởi cleanup success. Gracefully stop server/tcpdump theo PID do wrapper quản lý; timeout rồi báo trạng thái. Clear-netem không xóa network namespace; teardown xóa IFB/filter/veth/namespaces do lab sở hữu. Không tác động interface/route ngoài lab.

## 7. Thiết kế thí nghiệm

**Bulk performance:** cold connection mỗi trial, 6×1MiB, 30 repeats/transport/scenario chính +2 warm-up, instrumentation nặng tắt. Config/workload/network giống nhau; ghi CC, CPU/userspace/kernel/TLS/scheduling khác biệt như limitation. Không có numeric superiority gate.

**Handshake:** 1×1024 bytes, rtt50-loss0, 30 measured/cold,resumed,early, cùng QUIC implementation. Mỗi resumed/early measured trial có warm-up riêng tạo ticket; log warm-up ngoài aggregate. Cache rỗng cho cold. Server process không restart giữa warm-up/target. Nếu state không đạt mode dự định, giữ row và phân loại failed demonstration hoặc actual fallback, không gộp vào accepted-early distribution.

**HOL evidence:** instrumentation on, bulk/rtt50-loss3, bounded tối đa 10 attempts tìm trace có loss/gap phù hợp và giữ toàn bộ attempts. TCP gap + bytes sau gap ở capture và ứng dụng stall; QUIC loss/ranges + stream khác tiếp tục deliver trong progress/qlog. Nếu không đủ correlate, ghi inconclusive và dùng giải thích chuẩn + kết quả performance, không dựng trace. Không hứa random loss sẽ cho một stream chậm rõ ràng mỗi lần. Nếu thêm targeted loss test sau này phải có spec riêng; không thay bằng sleep trên một stream rồi gọi đó là network HOL.

## 8. qlog, Wireshark và privacy của demo

Bật qlog đúng API phiên bản; QLOGDIR không được unset khi chạy evidence. Trace phải flush/parse được, đúng connection. Kiểm tương thích qvis schema trước buổi diễn; không mặc định đổi đuôi .sqlog thành .qlog sẽ chuyển format.

Capture TCP/UDP port4433 trong namespace hoặc interface biết rõ path. Sender capture có thể thấy packet trước khi netem drop; không dùng riêng nó chứng minh receiver đã nhận. Dùng paired capture khi cần; mô tả capture point. QUIC Initial có thể được dissector nhận diện, Handshake/1-RTT payload cần secrets để xem sâu; keylog bật riêng evidence và cấu hình Wireshark đúng. Server response không phải “server gửi 0-RTT”: early-data level là client→server.

Performance metrics lấy từ client, không từ Wireshark timestamps. qvis offline/screenshots/recording dự phòng phải gắn label pre-recorded và run_id thật. Không upload capture/secrets lên public service mặc định; qvis local hoặc artifact demo đã kiểm tra phù hợp.

## 9. P8 implementation và gate hiện hành (2026-10-01)

P7 recovery/rerun đã PASS; giữ lịch sử IFB failure và first-load sau fresh boot chưa kiểm. P8 `netem.sh`, `clear-netem.sh`, `inspect.sh` dùng lock/ownership P7, Python state helper đọc strict config và đối chiếu tc JSON. Main flower chọn exact source/destination IPv4 hai lab endpoints, mirred egress redirect đến receiver ifb0; không chọn ResourceID hoặc DATA packet. Netem handle1: trên IFB, không trên eth0 trong ingress-ifb. Egress-demo clear ingress/filter/IFB netem trước khi netem trên eth0; switch lại cũng reset. Reserved handles chỉ được clear khi kind/filter phù hợp, foreign state bị từ chối. Invalid config không thay profile cũ; tc/offload/verification failure sau bắt đầu apply rollback impairment và giữ nonzero, không publish verified state.

Offload before/after/actions lưu cho eth0/ifb0 hai namespaces; tắt TSO/GSO/GRO, tx-udp-segmentation, rx-udp-gro-forwarding, rx-gro-list nếu mutable/ON. Fixed/absent không giả được sửa; bất kỳ feature liên quan còn ON đều chặn verified apply. Clear giữ offload OFF trên disposable devices đến teardown. Seed default lấy config base_seed; actual seed phải xuất hiện đúng trong tc JSON. Nếu không hỗ trợ, fail và chẩn đoán; muốn chạy không seed phải chọn explicit `--seed=none`, snapshot/CSV null kèm disabled-explicitly. Không claim TCP/QUIC dùng identical loss trace.

Actual state snapshots ra stdout, metadata root-owned lưu /run/quic-performance-lab/impairment-v1.json, xóa khi clear/teardown. Client đọc snapshot recent<=5 phút, kiểm qclient namespace identity rồi gắn network fields/evidence labels; snapshot không khóa kernel xuyên transfer. Runner inspect trước/sau, reset khi idle, sau probes. tc JSON theo upstream iproute2: delay object đơn vị seconds, loss fraction, rate object bytes/s; raw JSON và human `tc -s -d` đều giữ để review parser/units trên iproute2 thực. Nguồn: [netem manual](https://man7.org/linux/man-pages/man8/tc-netem.8.html), [q_netem source](https://github.com/iproute2/iproute2/blob/main/tc/q_netem.c), [mirred source](https://github.com/iproute2/iproute2/blob/main/tc/m_mirred.c), [rate JSON source](https://github.com/iproute2/iproute2/blob/main/lib/json_print.c). Đây là source review, không thay actual verification trên kernel.

G08 runner: 12 ping/mỗi chiều baseline và rtt50-loss0 (baseline<10ms, rtt50 40..60ms); reset rồi TCP/QUIC bulk qua bốn main scenarios, kiểm raw/CSV hash, phase=evidence, matching config/seed, IFB và redirect counters tăng hai hướng, downstream bytes dominate bulk, sustained goodput>0 và <=110% configured rate. Counter deltas giữ bytes/packets/drops/overlimits; raw snapshots giữ backlog/queue. Chuyển egress-demo↔ingress, clear hai lần, actual tc parser error sau qclient apply, teardown và runner SIGINT exit130, host link/address/route so sánh đều nằm trong gate. Không có numeric QUIC-superiority gate. G08 actual rerun PASS tại results/p8-g08-96nOtS/: main exit0/cleanup0, tám successful trials; SIGINT child130/cleanup0 tại p8-g08-qOYl2H. Agent review probes/kernel snapshots/raw/CSV/host ở evidence/p8/g08-rerun-review.json. Không mở main cohort P9 trước actual G08 verified. Runbook: evidence/p8/README.md.

P8 baseline refinement: trong namespace đã xác thực ownership, root handle `0:` là baseline kernel. Chấp nhận `noqueue`, hoặc `fq_codel` chỉ trên `ifb0`; clear giữ nguyên baseline, chỉ xóa reserved netem/ingress. Không chấp nhận fq_codel có handle khác hoặc trên eth0. G08 lần đầu actual FAIL trước probe/trial; host final unchanged, topology removed. User actual rerun đã PASS sau fix; giữ nguyên first-fail log/provenance.

## 10. P9 orchestration và G09 hiện hành

`scripts/bench.sh` theo plan/entry/merge của §6; binaries, dependencies và cert chuẩn bị bằng user trước sudo. Tạo full schedule một lần, paired AB/BA cân bằng, seed đổi mỗi pair và reset lại trước TỪNG transport sau probes. Chạy 12 no-loss RTT samples/mỗi chiều baseline/rtt50-loss0 và verify tolerance trước measured trials; không background ping/trace trong transfer. Managed server TCP/UDP :4433 ở qserver, cold bench ở qclient, UID/GID thường; timeout process chỉ quản lý descendant của wrapper.

Trước/sau từng invocation có verified ingress snapshot và checks config hash/scenario/seed/namespace, counters/mirred direction, rate upper sanity trên success. Sau client Close, chờ queue drain/counters quiet; transfer failure có raw hợp lệ đợi hết server trial deadline trước khi tiếp tục reset. Infra apply/inspect/metadata/write/missing error dừng cohort và merge đầy đủ lịch, giữ source shards. Cleanup dừng managed processes, clear/teardown và byte-compare host link/address/route. Snapshot vẫn không continuous lock; không thay đổi mạng lab đồng thời. SIGKILL của wrapper không trap được.

Full G09 `sudo bash tests/system/run.sh --gate G09`: actual interrupted transfer riêng (exit130, missing/not-started rows, cleanup), rồi main240 measured+16 warmup, stream rows1536, manifests/raw/shards/probes/network, CSV-derived summary và tám plot exports. Failed transfers vẫn được báo và có thể tồn tại trong dataset hợp lệ; không có QUIC-superiority gate. Missing/infra/cleanup trong main thì không PASS. Code/software checks PASS. Actual user rerun **G09 PASS** tại results/p9-g09-8dFdkj: main256 success/1536 resources, four probes, controlled child130 và cả hai cleanup0; evidence/p9/g09-rerun-review.json kiểm hashes/network/idle/CSV/stats. Interactive terminal Ctrl+C qua tee từng exit141/cleanup1 vẫn còn limitation; controlled child PASS không xác minh lại đường terminal đó. Reproduction/evidence: [P9 runbook](evidence/p9/README.md). Không mở P10.
