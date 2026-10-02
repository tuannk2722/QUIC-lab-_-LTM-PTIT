# Version lock và kiểm chứng API

Status toolchain P0 (2026-09-30): **VERIFIED; primitive probe PASS; G00 PASS**. Bảng dưới giữ chứng cứ P0 lịch sử; pins không đổi trong P10. P9/G09 đã PASS theo hồ sơ/xác nhận người dùng; P10 actual G10 user-run đã PASS; P11 software evidence được kiểm, actual capture gate BLOCKED. Gate/evidence hiện hành ở [ACCEPTANCE_RESULTS](ACCEPTANCE_RESULTS.md), [P9](evidence/p9/README.md) và [P10](evidence/p10/README.md).

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
| tcpdump / Wireshark / qvis | tcpdump4.99.6; P11 local tshark4.6.4 version/fields verified, quic-12 PNG viewer opened; actual PCAP decode BLOCKED | doctor-host.txt |

Nguồn tải [Go 1.27.1](https://go.dev/dl/#go1.27.1), [quic-go v0.63.0](https://github.com/quic-go/quic-go/releases/tag/v0.63.0). SHA-256 archive Linux amd64 được đối chiếu metadata chính thức trước giải nén: `63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445`. Makefile ép đúng Go 1.27.1, GOTOOLCHAIN=local, build/test -mod=readonly; go.mod/go.sum pin dependency. Không tạo commit trong lượt P0 này. Lệnh tái lập ở README.

## Cấu hình QUIC từ P4, cập nhật P10

`internal/transport/quic/config.go` dùng quic-go v0.63.0, QUIC v1. P10 server dùng `quic.ListenEarly`; cold/resumed clients dùng `quic.Dial`, early dùng `quic.DialEarly`. Server có `MaxIncomingStreams=64`; client đặt `-1` để từ chối server-initiated bidirectional streams. Hai phía có `MaxIncomingUniStreams=-1`; `InitialStreamReceiveWindow=512 KiB`, `MaxStreamReceiveWindow=2 MiB`; `InitialConnectionReceiveWindow=2 MiB`, `MaxConnectionReceiveWindow=16 MiB`. Các giá trị này là flow-control credits; không đồng nghĩa 16 MiB đã cấp phát cho từng connection. quic-go cho phép tổng handshake tối đa 2× `HandshakeIdleTimeout`, nên mã đặt idle timeout bằng một nửa giới hạn handshake cấu hình (mặc định 5s để giữ tổng tối đa 10s); client còn dùng dial context 10s và trial context 60s mặc định.

Server CLI bind TCP/UDP cùng số port trước readiness, dùng một certificate và một `*workload.Store`, cùng limiter tối đa 8 connections đang xử lý. Client QUIC ghi native `StreamID()` thực bên cạnh ResourceID; không suy ID từ thứ tự resource. P10 `--allow-0rtt` điều khiển `Config.Allow0RTT` (default true) với ListenEarly; qlog/capture/trace decoder thuộc P11. Các gate/functionality và giới hạn actual testbed nằm ở ACCEPTANCE_RESULTS.

### P10 — early APIs và lifecycle đúng tag v0.63.0

- [ListenEarly/Allow0RTT](https://github.com/quic-go/quic-go/blob/v0.63.0/server.go): listener trả `*EarlyListener`, Accept trả connection có thể trước handshake. [DialEarly](https://github.com/quic-go/quic-go/blob/v0.63.0/client.go) trả `*Conn`; return chỉ là early readiness. Observer bắt đầu ngay khi connection được API cung cấp; secure completion/Used0RTT/DidResume được quan sát riêng, không hardcode.
- [NextConnection/Err0RTTRejected](https://github.com/quic-go/quic-go/blob/v0.63.0/connection.go): NextConnection đợi handshake hoặc trả cancellation/connection failure, reset stream maps rồi trả chính `*Conn` hiện tại. Đây là chuyển connection sang dùng 1-RTT, không Dial connection mới. Quic-go bỏ early data bị rejected; application cần replay nếu workload cho phép.
- Lab giữ một coordinator cho toàn batch: join workers cũ trước NextConnection, replay tối đa một lần với t0 gốc và final attempt index1. Không CancelRead/CancelWrite trên streams đã bị quic-go invalidate do rejection: queued cancellation có thể ảnh hưởng IDs dùng lại sau reset. Valid-ticket forced rejection giữ TLS ticket keys/ALPN và đổi Allow0RTT bằng config hook; kiểm actual DidResume=true/Used0RTT=false và đúng bytes/hash, không xóa cache để giả rejection.
- `internal/tlsconfig/sessioncache.go` dùng thread-safe LRU cache một entry cho riêng sequence; non-nil Put signal ticket đã đến, Wait có context deadline. Prior cold transfer có t0 riêng; resumed/early target cùng server process nhưng t0 target mới. Failure/cancel trước successful handshake không gán bool state giả.
- Acceptance API qualification cần REQUEST write thành công (`request_end_ms`) trước observed handshake cùng actual Used0RTT/DidResume, no rejection/fallback. Observer có scheduling delay; API enqueue không chứng minh packet ra NIC. P11 packet/qlog corroboration chưa thực hiện; actual ingress G10 đã PASS ở user-run; G11 capture proof BLOCKED. [Evidence/checks P10](evidence/p10/README.md).

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
- `Conn.HandshakeComplete() <-chan struct{}`, `ConnectionState().Used0RTT`, `.TLS.DidResume`; `Err0RTTRejected` và `NextConnection(ctx) (*Conn,error)` tồn tại. P0 chỉ compile/source-check; P10 đã thêm actual functional rejection/replay và handshake/cancellation checks. Xem `evidence/p0/api-next-connection.txt` và evidence P10.
- `Config.Tracer func(context.Context, bool, ConnectionID) qlogwriter.Trace`; qlog.DefaultConnectionTracer dùng QLOGDIR, file `<odcid>_<perspective>.sqlog`; nil nếu biến môi trường rỗng. Format sequential JSON, event schema `urn:ietf:params:qlog:events:quic-12`. P11 actual qlog flush/parse và PNG viewer đã PASS localhost; capture/PCAP decode actual BLOCKED.
- Các field flow-control/stream limits, Versions/Version1 và timeout được compile-check. `HandshakeIdleTimeout` không phải tổng deadline: thư viện dùng tối đa 2× giá trị này cho handshake; phase transport phải giữ deadline của lab.
- [Nguồn congestion đúng tag](https://github.com/quic-go/quic-go/blob/v0.63.0/internal/ackhandler/sent_packet_handler.go) gọi NewCubicSender với `true // use Reno`; không gán nhãn CUBIC chỉ từ tên constructor. Trích source ở api-congestion.txt; CC của TCP chưa đo.
- Ở P0, TLS cache interface và trust/SAN/TLS1.3/ALPN policy được kiểm tra, chưa chạy ticket delivery/0-RTT. P10 đã triển khai/kiểm functional ticket notification và actual state; P0 không tạo manifest benchmark hay kết quả Used0RTT giả.

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

## P11 observability/decoder receipt

D28 current: Go pin1.27.1/quic-go v0.63.0 giữ nguyên, nhưng make build/test/test-race áp local build-only crypto/tls keylog overlay. Đây không phải stdlib nguyên bản: generator kiểm version và SHA256 upstream sources, thêm hai optional early keylog calls, không sửa GOROOT/module cache hoặc crypto algorithm. Exact original/overlay hashes nằm trong bin/build.json và [actual early export review](evidence/p11/g11-early-secret-review.json); [patch](evidence/p11/g11-early-overlay.patch). Actual cold/resumed/accepted/rejected/writer-errors và full Go/race PASS. Historical P0/P10 receipts giữ nguyên; current full PCAP/IFB G11 vẫn chờ sudo actual run. Reproduction bằng make, không standalone go build thiếu overlay.

Pinned module giữ v0.63.0; installed source qlog/qlogwriter xác minh `NewConnectionFileSeq`, `FileSeq.Run`, `Trace.AddProducer` và last-producer Close drains writer, schema `urn:ietf:params:qlog:events:quic-12`, RS JSON-SEQ. Actual12 connection traces (6 client+6 server) parsed/correlated trong localhost software; keylog/progress/rejection/flush/race checks ở [P11](evidence/p11/README.md). Source API: [qlogwriter đúng tag](https://github.com/quic-go/quic-go/blob/v0.63.0/qlogwriter/writer.go).

Local decoder tshark4.6.4-1 từ Ubuntu26.04 archive packages, extracted `.tools/tshark` UID1000; không hệ thống/root install. Version/fields/plugin loading verified; hashes/exact transitive package versions ở `analysis/decoder-packages.json` và [receipt](evidence/p11/g11-decoder-receipt.json). `make decoder-deps` kiểm bytes trước extract. Host base shared libraries vẫn do Ubuntu cung cấp, không claim fully portable bundle. [Tshark manual](https://www.wireshark.org/docs/man-pages/tshark.html) và [QUIC fields](https://www.wireshark.org/docs/dfref/q/quic.html) hỗ trợ adapter; chưa được kiểm trên captured G11 PCAP vì sudo authentication. Viewer PNG/SVG đã rendered/opened; standalone HTML generated nhưng browser/qvis chưa tested.
