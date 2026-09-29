# Version lock và kiểm chứng API

Status: **UNRESOLVED — phải hoàn thành ở P0 trên Ubuntu VM**. Không có Go module/source application trong gói handoff ban đầu; không bịa pin hoặc tuyên bố build được.

| Thành phần | Giá trị cần điền | Evidence |
|---|---|---|
| Ubuntu/kernel | UNRESOLVED | os-release, uname |
| VM hypervisor/vCPU/RAM | UNRESOLVED | actual environment |
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
