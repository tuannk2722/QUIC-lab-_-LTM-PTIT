# Version lock và kiểm chứng API

Status P0 (2026-09-30): **toolchain/API/build VERIFIED; primitive probe PASS; G00 tổng thể PASS**. Bảng dưới ghi chứng cứ P0 lịch sử; các phase P1–P3 đã bổ sung workload/TCP và mã P4 đã thêm QUIC cold. Trạng thái G04 nằm ở ACCEPTANCE_RESULTS; chưa có benchmark.

| Thành phần | Giá trị / trạng thái P0 | Evidence |
|---|---|---|
| Host OS / WSL version | Windows 11 / 3.0.1.0: user-reported, chưa xác minh lại qua Windows CLI | Quan sát lịch sử bên dưới |
| Linux distribution / kernel | Ubuntu 26.04.1 LTS / 6.18.40.1-microsoft-standard-WSL2 | evidence/p0/doctor-host.txt |
| Logical CPU / RAM / swap | 2 / 3053154304 bytes / 2147483648 bytes | doctor-host.txt; tài nguyên quan sát, không bảo đảm độc quyền |
| Go exact version | **1.27.1**, linux/amd64; cài local .tools/go1.27.1, không root | toolchain.json, g00-commands.log |
| quic-go exact module tag | **v0.63.0** | go.mod/go.sum, modules.txt, modules-verify.txt |
| quic-go minimum Go | **1.26.0** theo go.mod đúng tag | [go.mod chính thức](https://github.com/quic-go/quic-go/blob/v0.63.0/go.mod) |
| iproute2 / netem / IFB / mirred / ethtool | ip/tc 6.19.0; ethtool 6.19; sch_netem/ifb/act_mirred hiện diện | doctor-host.txt; network-probe.log: người dùng chạy thành công ngày 2026-09-30, kèm provenance/hash |
| Git / make / OpenSSL | 2.53.0 / 4.4.1 / 3.5.5 | doctor-host.txt |
| Python / plotting | P0: 3.14.4/chưa plotting. P9: Python3.14.4, Matplotlib3.10.8 và toàn bộ transitive versions pinned trong analysis/requirements.txt, installed .tools/analysis UID thường | doctor-host.txt; evidence/p9/g09-analysis-install.log; actual software plots |
| tcpdump / Wireshark / qvis | tcpdump 4.99.6; decode/viewer chưa kiểm chứng, để P11 | doctor-host.txt |

Nguồn tải [Go 1.27.1](https://go.dev/dl/#go1.27.1), [quic-go v0.63.0](https://github.com/quic-go/quic-go/releases/tag/v0.63.0). SHA-256 archive Linux amd64 được đối chiếu metadata chính thức trước giải nén: `63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445`. Makefile ép đúng Go 1.27.1, GOTOOLCHAIN=local, build/test -mod=readonly; go.mod/go.sum pin dependency. Không tạo commit trong lượt P0 này. Lệnh tái lập ở README.

## Cấu hình QUIC trong mã P4

`internal/transport/quic/config.go` dùng quic-go v0.63.0, QUIC v1 và `quic.Listen`/`quic.Dial` cho cold path. Server có `MaxIncomingStreams=64`; client đặt `-1` để từ chối server-initiated bidirectional streams. Hai phía có `MaxIncomingUniStreams=-1`; `InitialStreamReceiveWindow=512 KiB`, `MaxStreamReceiveWindow=2 MiB`; `InitialConnectionReceiveWindow=2 MiB`, `MaxConnectionReceiveWindow=16 MiB`. Các giá trị này là flow-control credits; không đồng nghĩa 16 MiB đã cấp phát cho từng connection. quic-go cho phép tổng handshake tối đa 2× `HandshakeIdleTimeout`, nên P4 đặt idle timeout bằng một nửa giới hạn handshake cấu hình (mặc định 5s để giữ tổng tối đa 10s); client còn dùng dial context 10s và trial context 60s mặc định.

Server CLI P4 bind TCP/UDP cùng số port trước readiness, dùng một certificate và một `*workload.Store`, cùng limiter tối đa 8 connections đang xử lý. Client QUIC ghi native `StreamID()` thực bên cạnh ResourceID trong output tối thiểu; không suy ID từ thứ tự resource. `--allow-0rtt` chưa dùng `ListenEarly`; resumption/early, qlog và xác minh trace thuộc P10/P11. G04 transfer/race thực đã PASS theo `docs/ACCEPTANCE_RESULTS.md`; phần này ghi cấu hình mã.

## API checklist đã kiểm chứng ở P0 (compile/source; chưa chạy QUIC)

- QUIC Dial/Transport/DialEarly, Listen/ListenEarly, Accept signatures/context.
- Conn/Stream concrete types; OpenStream/OpenStreamSync; AcceptStream; StreamID; Close/CancelRead/CancelWrite và deadlines.
- HandshakeComplete, ConnectionState().Used0RTT và TLS.DidResume ở đúng types.
- Err0RTTRejected, API chuyển sang tiếp tục 1-RTT (ví dụ NextConnection) và cancellation.
- qlog tracer signature/constructor/output extension/format; không trộn ví dụ `logging.ConnectionTracer` cũ với `qlogwriter.Trace` mới.
- Config Version1, stream/flow-control/idle/handshake limits; thư viện CC default thực tế.
- TLS ClientSessionCache wrapper/ticket notification; `crypto/tls` trust và keylog concurrency.

Lưu source tag/link và `go doc` output ngắn chứng minh. Nếu official web snippets mâu thuẫn với installed source, installed pinned API quyết định code, update docs/decision; không đổi ngầm behavior yêu cầu. Chạy compile smoke trước triển khai QUIC đầy đủ.

### Kết quả API đúng tag v0.63.0

- Dial/DialEarly trả `*quic.Conn`; Listen/ListenEarly trả `*Listener`/`*EarlyListener`; Accept(ctx) trả `*Conn`. Streams là `*quic.Stream`. Compile signature checks ở `tests/api/quic_test.go` (không mở socket).
- `Conn.HandshakeComplete() <-chan struct{}`, `ConnectionState().Used0RTT`, `.TLS.DidResume`; `Err0RTTRejected` và `NextConnection(ctx) (*Conn,error)` tồn tại. Sau rejection phải gửi lại request ở phase P10; API có thể trả lỗi handshake/cancellation. Xem `evidence/p0/api-next-connection.txt`.
- `Config.Tracer func(context.Context, bool, ConnectionID) qlogwriter.Trace`; qlog.DefaultConnectionTracer dùng QLOGDIR, file `<odcid>_<perspective>.sqlog`; nil nếu biến môi trường rỗng. Format sequential JSON, event schema `urn:ietf:params:qlog:events:quic-12`. Viewer/flush/capture thực vẫn thuộc P11, không được coi là đã pass.
- Các field flow-control/stream limits, Versions/Version1 và timeout được compile-check. `HandshakeIdleTimeout` không phải tổng deadline: thư viện dùng tối đa 2× giá trị này cho handshake; phase transport phải giữ deadline của lab.
- [Nguồn congestion đúng tag](https://github.com/quic-go/quic-go/blob/v0.63.0/internal/ackhandler/sent_packet_handler.go) gọi NewCubicSender với `true // use Reno`; không gán nhãn CUBIC chỉ từ tên constructor. Trích source ở api-congestion.txt; CC của TCP chưa đo.
- TLS cache interface và trust/SAN/TLS1.3/ALPN policy được kiểm tra; ticket delivery/0-RTT thực chưa triển khai. P0 không tạo manifest benchmark hay kết quả Used0RTT giả.

## Quan sát trước P0 do người dùng cung cấp — 2026-09-30

Nguồn: thông tin/preflight đã kiểm chứng do người dùng cung cấp cho migration tài liệu; agent không chạy lại ở lượt này. Đây là observations, không phải architectural pins; P0 phải revalidate và lưu command/output thực. Tại thời điểm migration, Go/quic-go chưa pin hoặc test; trạng thái P0 hiện tại ở đầu tài liệu.

| Hạng mục | Quan sát |
|---|---|
| Host / execution layer | Windows 11 / Ubuntu dưới WSL2 |
| WSL version / Linux kernel | 3.0.1.0 / 6.18.40.1-1 |
| Resource limits configured/observed | Khoảng 3 GB RAM, 2 logical processors, 2 GB swap |
| GUI / IDE | Linux GUI không cần; Windows VS Code Remote WSL, workspace `WSL: Ubuntu` |
| Repo hiện tại | `/home/tuannk/projects/QUIC-lab-_-LTM-PTIT` (native Linux filesystem) |
| Git | 2.53.0 |
| iproute2 / ip / tc | 6.19.0 |
| tcpdump | 4.99.6, available |
| Python | 3.14.4 |
| ip netns | PASS: qclient/qserver tạo và xóa được |
| veth | PASS: pair tạo và xóa được |
| tc/netem | PASS: gắn qdisc 50 ms thành công |
| IFB | PASS: module/device tạo được và device UP |
| act_mirred | PASS: module load thành công |

Preflight chỉ chứng minh primitives, không pass G07/G08. P0 xác minh lại versions/capabilities phù hợp; P5/P6 triển khai manifest phân biệt host OS, execution/virtualization layer, distro/kernel, CPU/RAM/swap và WSL/VM version nếu áp dụng theo METRICS§5. Nếu cần schema migration, ghi follow-up có version khi triển khai; lượt này không đổi schema/CSV.
