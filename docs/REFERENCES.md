# References và provenance

## Tệp người dùng cung cấp

Giữ nguyên tại `references/originals/`; xem `references/SOURCE_MANIFEST.json` cho SHA-256, byte size và line count. Hai bản T03 giống hệt nhau; không xóa bản (1) để người dùng còn đối chiếu. Những file này là tài liệu tham khảo, không phải kết quả benchmark.

## Nguồn chính thức được kiểm tra khi tạo handoff (28/09/2026)

| ID | Link | Dùng cho |
|---|---|---|
| W01 | https://quic-go.net/docs/quic/client/ | Cache/resumption, early API, rejected early, transition API cần pin |
| W02 | https://quic-go.net/docs/quic/server/ | ListenEarly, Allow0RTT, actual state |
| W03 | https://quic-go.net/docs/quic/streams/ | Stream abstraction/open/accept/lifecycle |
| W04 | https://quic-go.net/docs/quic/qlog/ | Tracer/QLOGDIR, streaming format/viewer; API theo version |
| W05 | https://man7.org/linux/man-pages/man8/tc-netem.8.html | Delay/loss/rate/seed/limitations và receiver ingress với TSQ |
| W06 | https://www.rfc-editor.org/rfc/rfc9000.html | Transport stream/packet/CID nền tảng |
| W07 | https://pkg.go.dev/time | Monotonic durations, không persist monotonic clock qua serialize |
| W08 | https://github.com/quic-go/quic-go/releases | Release changes; khóa tag ở P0, không lấy webpage latest làm lockfile |

Nguồn web là tài liệu sống, không thay kiểm chứng API của module đã pin. Những ràng buộc như QB01/limits/schedule/IFB wrappers là quyết định thiết kế lab, không phải requirement của RFC.

## RFC từ tài liệu gốc để đọc sâu

- [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html) — transport, streams, frames, connections.
- [RFC 9001](https://www.rfc-editor.org/rfc/rfc9001.html) — TLS integration/early data.
- [RFC 9002](https://www.rfc-editor.org/rfc/rfc9002.html) — loss detection/congestion control.
- [RFC 8999](https://www.rfc-editor.org/rfc/rfc8999.html) — version-independent properties.
- [RFC 9114](https://www.rfc-editor.org/rfc/rfc9114.html) — HTTP/3, chỉ đối chiếu scope.
- [RFC 9308](https://www.rfc-editor.org/rfc/rfc9308.html) — applicability/trade-offs.

Không nói RFC9002 buộc mọi library dùng cùng một CC implementation. Khi viết báo cáo thật, dẫn source theo claim và dùng phiên bản/thời điểm tương ứng. Không sao chép ví dụ code/documentation lớn mà không attribution/license.
