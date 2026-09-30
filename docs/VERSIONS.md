# Version lock và kiểm chứng API

Status: **UNRESOLVED — phải hoàn thành ở P0 trên Ubuntu WSL2**. Không có Go module/source application trong gói handoff ban đầu; không bịa pin hoặc tuyên bố build được.

| Thành phần | Giá trị cần điền | Evidence |
|---|---|---|
| Host OS / execution environment / WSL hoặc VM version (nếu áp dụng) | P0 revalidate | actual environment; observations below |
| Linux distribution/release / kernel | P0 revalidate; Ubuntu release UNRESOLVED | os-release, uname |
| Allocated logical CPU / RAM / swap | P0 revalidate | actual limits and observed resources |
| Go exact version | UNRESOLVED | go version |
| quic-go exact module tag | UNRESOLVED | go.mod/go.sum + go list -m |
| quic-go minimum Go | UNRESOLVED | go.mod của đúng tag |
| iproute2/netem/IFB/ethtool | UNRESOLVED | tool versions + scoped capabilities |
| Python/plot libs | UNRESOLVED | pinned requirements + version report |
| Wireshark/tcpdump/qvis/schema | UNRESOLVED | actual parse/open evidence |

P0 chọn stable released Go/quic-go tương thích, pin exact versions; commit go.mod/go.sum. Có thể dùng Go đang có nếu support đúng library; nếu cần install thì hướng dẫn phù hợp OS và quyền. Không hardcode “latest”. Các command tái lập sau P0 dùng version đã pin, không floating tag.

## API checklist phải giải quyết trước implementation

- QUIC Dial/Transport/DialEarly, Listen/ListenEarly, Accept signatures/context.
- Conn/Stream concrete types; OpenStream/OpenStreamSync; AcceptStream; StreamID; Close/CancelRead/CancelWrite và deadlines.
- HandshakeComplete, ConnectionState().Used0RTT và TLS.DidResume ở đúng types.
- Err0RTTRejected, API chuyển sang tiếp tục 1-RTT (ví dụ NextConnection) và cancellation.
- qlog tracer signature/constructor/output extension/format; không trộn ví dụ `logging.ConnectionTracer` cũ với `qlogwriter.Trace` mới.
- Config Version1, stream/flow-control/idle/handshake limits; thư viện CC default thực tế.
- TLS ClientSessionCache wrapper/ticket notification; `crypto/tls` trust và keylog concurrency.

Lưu source tag/link và `go doc` output ngắn chứng minh. Nếu official web snippets mâu thuẫn với installed source, installed pinned API quyết định code, update docs/decision; không đổi ngầm behavior yêu cầu. Chạy compile smoke trước triển khai QUIC đầy đủ.

## Quan sát máy hiện tại — 2026-09-30

Nguồn: thông tin/preflight đã kiểm chứng do người dùng cung cấp cho migration tài liệu; agent không chạy lại ở lượt này. Đây là observations, không phải architectural pins; P0 phải revalidate và lưu command/output thực. Go/quic-go chưa pin hoặc test; G00 chưa chạy.

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
