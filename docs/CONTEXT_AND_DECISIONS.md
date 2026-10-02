# Context và quyết định

### D29 — 2026-10-02: sửa sbin PATH sau reset-env của P11

- Actual user-run `results/p11-g11-1200e3df1cf2` FAIL trước setup/trial:23 planned,0 invoked, original1/cleanup0, host link/address/route unchanged. Log `evidence/p11/g11-user-run.Jbm1be.log` và14 artifacts giữ nguyên hashes. Đây là lỗi runner, không phải thiếu procps hoặc lỗi early-secret export.
- sysctl có tại /usr/sbin/sysctl; setpriv reset-env tạo non-root PATH thiếu sbin. G11 owner helper, capture helpers/sinks và namespace entry explicit trusted PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin sau reset-env. HOME/USER/LOGNAME vẫn từ passwd; root XDG/Wireshark settings vẫn loại bỏ, UID/group policy và seed giữ nguyên. Không inherit arbitrary root/user PATH để sửa lookup.
- G11 preflight thêm sysctl và kiểm utilities qua owner helper trước prepare/topology. Regression thực chạy đúng bench-support runtime qua production helper với real setpriv/reset-env/real sysctl bằng UID1000 (chỉ init-groups thay keep-groups để test không cần root);7 socket/CC sysctls đọc được,8 utilities resolve.9 lifecycle/environment/metadata/checker tests PASS. Không dùng metadata-only run làm full network proof.
- Requirements: NETWORK§6/§12, CLI privilege/evidence, PLAN P11/G11. No Go/dependency/pin/crypto changes; giữ previous suite/race PASS, không rerun dư thừa. Full G11 retry dùng cùng ordinary-user command `bash scripts/run-g11-review.sh`.

### D28 — 2026-10-02: hoàn tất đường xuất early keylog cho P11

- User yêu cầu tiếp tục hoàn thành P11/G11; đây là authorization mới sau checkpoint bugfix D27. Không mở P12 hoặc commit. Latest actual5/23 FAIL vẫn giữ nguyên; bản sửa chưa được gán vào provenance lịch sử.
- Go1.27.1 đã tính early secret và chuyển cho QUIC nhưng thiếu writeKeyLog ở hai early paths. `scripts/tls_keylog_overlay.py` dùng official Go `-overlay`: kiểm exact version + SHA256 hai upstream source files, tạo bản sao build-only với một optional `Config.writeKeyLog("CLIENT_EARLY_TRAFFIC_SECRET", clientRandom, earlyTrafficSecret)` ở mỗi phía, propagate lỗi bằng existing internal-error alert. Không thêm key derivation/packet crypto, không chỉnh installed GOROOT/module cache, không đổi Go/quic-go pins hoặc criteria. Đây là local observability patch của crypto/tls, không claim binary dùng stdlib nguyên bản.
- Client dùng random của transcript ClientHello; server dùng hs.clientHello.random. Keylog nil là existing no-op. Client thử early vẫn log khi server rejects; server chỉ log khi accepts. Existing TLS keylog mutex/sink0600/new-file-only giữ nguyên; không thêm response-write lock. Không export secret qua stdout, public archive hoặc qlog.
- `make build` tự chuẩn bị private hash-checked overlay; build receipt bind generator input và lưu original/overlay hashes. `make test`/`make test-race` dùng cùng overlay. Source drift hoặc generator/binary stale phải fail; không silent fallback. Manual Go build/test không qua Make phải explicit -overlay. Historical performance/source receipts không sửa; instrumentation off không ghi keylog.
- Actual localhost early secret client/server matches; cold/resumed không có early label, rejected chỉ client log và one replay; client/server keylog writer errors fail handshake. Full Go/race suites,4 provenance và8 lifecycle tests PASS. Actual software6 trials giữ5 successes +1 expected wrong-hostname TLS failure; API/qlog matches PN0/native stream0/32-byte range. Đây chưa là decrypted PCAP proof.
- G11 thêm early PCAP precheck sau3 handshake trials và trước20 bulk trials: cần decrypted QB01 REQUEST đúng PN/native stream/API ở cả captures; không thay full23 checker/HOL/cleanup. Ordinary-user `bash scripts/run-g11-review.sh` build rồi sudo và lưu log/PIPESTATUS. Agent sudo vẫn interactive authentication trước runner; chờ actual user-run, không tuyên bố G11 PASS.
- Sources: [official Go build overlay](https://pkg.go.dev/cmd/go#hdr-Compile_packages_and_dependencies), [TLS keylog format/early label](https://www.ietf.org/archive/id/draft-ietf-tls-keylogfile-04.html#section-2.1), local pinned Go crypto/tls early paths. Requirements: PLAN P11/G11, ACCEPTANCE Evidence/0RTT, NETWORK§8/§12, CLI optional evidence, TRACEABILITY rows18/20/25/26/28/29.

### D27 — 2026-10-02: sửa P11 lifecycle/environment/capture và thu gọn TASK

- User authorize sửa3 lỗi actual G11 và format TASK. Latest actual user-run `results/p11-g11-3344e60b5868`:23 planned/5 invoked/5 successful transfers; shutdown runner exit1, cleanup0 và host link/address/route unchanged. Checker chưa chạy;3 short-handshake captures chỉ có24-byte header. Log `evidence/p11/g11-user-run.DC0kWH.log` giữ nguyên; không nâng partial run thành PASS.
- G11/capture dùng shared child wait helper: missing/zombie process không còn được coi đang chạy, signal ESRCH được reaped bằng wait; child failure/forced KILL vẫn fail. Chỉ signal PID do caller tạo; bounded grace10s server/20s capture wrappers, tcpdump5s và sink5s mỗi sink. INT/TERM và cleanup errors được giữ.
- G11 UID helpers, capture sinks và namespace entry dùng setpriv --reset-env, tạo HOME/USER/LOGNAME/PATH đúng passwd owner và loại inherited root XDG/Wireshark settings; namespace vẫn clear supplementary groups, capture/file helpers vẫn init owner groups. G11 explicit NETEM_SEED được truyền lại cho manifest, không silent downgrade seed-null.
- tcpdump dùng --immediate-mode để đọc short traffic ngay, -U flush output từng packet; ngoài timing client, stop chờ reader200ms rồi SIGUSR2 flush/SIGINT và join EOF/fsync sinks. Capture receipt thêm actual PCAP record count/completeness/footer consistency; empty/truncated/count-mismatch fail, không dùng capture_drops=0 để suy PCAP đầy đủ. Archived checker audit lại bytes/footer kể cả receipt cũ mà không rewrite evidence.
- Software lifecycle/environment/count regressions, analysis/network checks và build receipt PASS. Agent rerun actual gate bản sửa vẫn bị sudo interactive authentication chặn trước runner; không automatic approval rejection hoặc topology mutation.
- Read-only decoder audit trên actual early-server PCAP đọc được UDP/1RTT, nhưng0RTT decryption failed và cả client/server keylogs thiếu CLIENT_EARLY_TRAFFIC_SECRET. Pinned Go1.27.1 crypto/tls/handshake_client.go và handshake_server_tls13.go chuyển early secret qua QUIC events, không gọi writeKeyLog ở early path; quic-go v0.63.0 public qlog key events không export secret bytes. Chưa có phương án export đã kiểm qua API pin; full early proof BLOCKED. Không đổi toolchain/module pins, patch cache/stdlib, tự derive keys hoặc giảm tiêu chí proof trong bugfix này. Cần review riêng phương án observability/version nếu xử lý export.
- TASK chuyển thành current checkpoint; bản279 dòng trước format giữ nguyên ở `.codex/history/TASK-2026-10-02-before-p11-fixes.md`. Lịch sử không là instructions/status hiện hành. Requirements: AGENTS continuity, PLAN P11/G11/continuity, NETWORK§8/§12, CLI privilege/capture, ACCEPTANCE Evidence/0RTT.

### D26 — 2026-10-02: P11 observability và conservative evidence gate

- User xác nhận P10/G10 PASS và authorize riêng P11/G11. Actual G10 user-run `results/p10-g10-cR1oR9` được checker audit trên copy,1836 archived artifacts byte-verified. Không tự nhận agent chạy sudo hoặc human code review. Checkpoints D25/P10 BLOCKED trước đó giữ lịch sử; P12 chưa authorize.
- Client/server `--qlog-dir` (default QLOGDIR) dùng đúng v0.63.0 `Config.Tracer` → `qlogwriter.NewConnectionFileSeq`, event schema `quic-12`, JSON-SEQ nguyên bản. Mapping client gắn run_id/target|ticket/ODCID; server nhiều connections đối chiếu shared ODCID và endpoint ports/addresses trong connection_started, không suy filename thứ tự. Sinks exclusive, bounded5s flush/error propagation sau shutdown; keylog thread-safe0600/new-file-only, giữ local. Performance bench từ chối traces; main artifacts không bị sửa/gộp.
- Progress mỗi resource/attempt giữ private slice cấp phát bounded trước t0 (ceil(size/16KiB)); recorded sau DATA frame được receiver validate, khi vượt threshold16KiB hoặc chunk cuối. Một frame lớn vượt nhiều thresholds có cùng observed frame-completion time; chunk nhỏ gộp đến threshold. Đây là refinement resolution của METRICS§4, không đổi first-DATA-byte hook G05, schema v1 hay timing formulas. Không ghi terminal/disk trong collection; flush sau workers/timing, prior ticket có file riêng, rejected attempt và replay giữ history/t0. Trace-mode guard ngăn pooling vào performance.
- G11 actual driver giữ plan23 invocations:3 handshake modes/rtt50-loss0 và10 cặp bulk TCP/QUIC/rtt50-loss3. Alternating order, seed2026100200 cho handshake và2026100201+i cho từng pair (explicit NETEM_SEED=none → null); reset/inspect/idle giữa runs. All attempts/failures giữ trong manifest/raw; chọn first pair có đủ witnesses, không sửa raw hoặc tạo targeted impairment. Apps/analysis/file sinks UID thường, privileged wrapper chỉ ownership/netns/qdisc/capture/process entry; experiment lock đóng fd ở children, graceful PID cleanup và host comparison.
- Paired tcpdump qclient/qserver eth0, snaplen0, readiness từ listening log, deadline<=300s, per-capture PID/drop/cleanup status. Eth0 ingress tap có thể trước IFB impairment: không coi packet thấy ở tap là application đã nhận; TCP ACK/SACK hoặc client qlog receive corroborates delivery. Tshark4.6.4 giải mã bằng local secrets; PDML adapter đọc native PN/STREAM và QB01 REQUEST32 bytes, từ chối association khi coalesced header tree ambiguous. Không tự QUIC crypto hoặc chế PCAP.
- Early proof cần API qualified + matched client-sent/server-received0RTT PN/stream range + decrypted PCAP chứa exact read-only QB01 REQUEST trên endpoint/stream target. HOL TCP cần cumulative ACK/SACK gap, bytes sau gap, sender retransmission và matching app stall. QUIC cần sender lost PN/ranges, client gap/later range, sibling payload progress độc lập với streams cùng lost packet, gap recovery trong PN mới. Correlation dùng same-host wall labels với3ms margin, không lấy chúng làm latency metrics; coarse progress có thể khiến INCONCLUSIVE. Completion bars hoặc lone loss event không proof; streams vẫn shared flow/congestion.
- Viewer local đọc schema thực, standalone HTML và Matplotlib PNG/SVG packet/progress timeline. PNG được mở kiểm thật; HTML chưa browser-render-test, không claim qvis compatibility. Decoder version/fields và local pinned packages verified; actual PCAP decode/loss/capture lifecycle chưa chạy vì sudo authentication chặn trước runner. G11 overall BLOCKED, independent software PASS; exact command và evidence tại `evidence/p11/README.md`.
- Requirements: SPEC§5–7, PROTOCOL§4/§6, METRICS§3–7, NETWORK§6–8, CLI trace/capture, PLAN P11/G11, ACCEPTANCE Evidence/0RTT và TRACEABILITY rows14/18/20/25/26/28/29. Originals/schema/configs/Go pins giữ nguyên.

### D25 — 2026-10-01: P10 ticket sequence, replay và handshake cohort

- User xác nhận P9/G09 PASS và cho phép riêng P10/G10. Các checkpoint D24/P9 cũ giữ lịch sử; không tự nhận đã rerun G09 của bản sửa hoặc human-review code. Tại checkpoint D25, P11/P12 vẫn chưa mở; D26 cập nhật phạm vi hiện hành.
- Mỗi QUIC sequence dùng TLS config clone và cache mới: cold không cache; resumed/early có một prior cold connection trong cùng process, chờ non-nil cache Put bằng notification/deadline trước target. Prior connection có t0 và directory `ticket-warmup/` riêng, không vào aggregate targets. Không dùng sleep để giả ticket sẵn sàng. Ticket/preparation thất bại tạo failed target slots, `target_invoked=false`, không dùng latency warm-up làm latency target.
- Suite handshake cố định QUIC, 1×1024 byte/chunk1024 và rtt50-loss0 (25ms/hướng, 20Mbps, loss0). Defaults 30 measured +2 phase warmups/mode =96 targets; resumed/early cần64 ticket warmups riêng. Six-permutation cycle có seeded starting order; measured30 cân bằng10/mode/vị trí. Mỗi triple cùng seed, đổi seed giữa triples; wrapper reset/inspect trước toàn sequence, khi server idle, giữ network condition qua prior+target và kiểm sau. Không reset giữa prior/target của cùng entry.
- Server dùng ListenEarly/Allow0RTT. Normal target Dial cho resumed, DialEarly cho early. Observer bắt đầu ngay khi early connection được trả và join trước đọc state; Handshake là thời điểm client quan sát, không backdate. Actual TLS DidResume/QUIC Used0RTT chỉ xác định sau observed handshake; Err0RTTRejected có thể xác định rejection trước handshake failure. EarlyReady chỉ là API readiness.
- Coordinator chờ mọi worker attempt0 dừng, ghi failed attempt rồi NextConnection đúng pinned API (cùng Conn), replay toàn read-only batch tối đa một lần với buffers/streams mới nhưng original t0. Không CancelWrite/CancelRead rejected streams đã bị quic-go invalidated: control frame của stream ID cũ có thể tác động ID được reset/reuse. Final bytes/hash chỉ tính receivers attempt cuối; history giữ bytes/timings/error từng attempt. Forced-rejection harness giữ valid ticket keys và đổi acceptance, kiểm sáu workers/one replay/6144 final bytes.
- Transfer success tách khỏi mode achieved. Early API qualification yêu cầu DidResume=true, Used0RTT=true, attempted=true, rejection=false, fallback0 và REQUEST write hoàn tất trước observed handshake. Fallback/unachieved được đếm, loại khỏi distribution của mode yêu cầu; không lọc mất failures. Đây chưa là packet proof: G11 mới bổ sung qlog/PCAP REQUEST trong packet0RTT.
- Watchdog handshake cho phép hai connection budgets (`2×timeout+15s`); timeout target vẫn một budget xuyên replay. Với1KiB không áp downstream5×upstream hoặc sustained-goodput20Mbps check của bulk; vẫn kiểm actual kernel/netem/filter/offload/counters/RTT/identity/cleanup. Không đổi schema v1, protocol, dependencies hoặc bulk cohorts.
- Requirements: SPEC§6, PROTOCOL read-only replay, METRICS§1/§3–7, NETWORK§5–7, CLI handshake/modes, PLAN P10/G10, ACCEPTANCE G10/G11, TRACEABILITY rows18/20–23/28/29. Evidence/status hiện hành tại `evidence/p10/README.md`.

### D24 — 2026-10-01: sửa audit lifecycle/concurrency/provenance P7–P9

- User cho phép sửa đúng năm findings audit; không mở P10. Wrapper giữ exclusive `experiment.lock` từ trước preflight topology đến hết cleanup; lock này riêng với lock thao tác qdisc, không giữ global QUIC response lock. Runner cạnh tranh bị từ chối exit3 trước plan. Các thao tác mạng thủ công vẫn không được chạy đồng thời với benchmark.
- Finalize merge/validate/summarize/plot ghi log bằng UID thường vào `logs/`; không phụ thuộc stdout của terminal/tee. Cleanup bỏ qua signal lặp trong lúc dọn hữu hạn, giữ exit130/143 gốc; trial đã dừng bởi SIGINT không bị xem là cleanup failure. Không trap được SIGKILL.
- Entry claim bằng hard-link publish nguyên tử tại `logs/<run_id>.claim.json` trước t0. Claim giữ sau crash/lỗi để không replay cùng scheduled observation. Merge chỉ nhận successful raw khi có invocation hoàn tất, exit0 và timestamps hợp lệ; missing journal → runner_error, unfinished → interrupted. INCOMPLETE giữ result_write_error; source raw không bị sửa.
- `make build` chạy Python helper bằng user, khóa build riêng, hash Go app inputs/mod/sum/Make/helper trước và sau build, publish ba binaries và `bin/build.json` sau cùng. Plan lưu receipt vào `build.json` và manifest; kiểm input inventory/binary hashes/current bench image. Entry kiểm lại receipt trước t0. Wrapper launch server/bench bằng file descriptor đã hash, không tra lại pathname sau verify; replacement/rebuild khác receipt làm nonzero trước transfer tiếp theo. Đây là reproducibility guard, không chống user cố ý sửa toàn bộ artifacts.
- Giữ schema kết quả v1, protocol, workload, timing và denominator. Analysis đọc legacy evidence không có receipt, nhưng checker G09 hiện tại yêu cầu receipt và completed journals, thêm actual competing-runner refusal trong interrupt case. Software checks không thay actual G09; evidence và trạng thái bản sửa tại `evidence/audit-p7-p9/`.
- Requirements: NETWORK§6/§10, METRICS§3–7, CLI bench/exit codes, PLAN P7–P9, ACCEPTANCE G06–G09; TRACEABILITY rows21–24/28/29. Không sửa evidence G09 đã thu hoặc tự nhận human review.

## 1. Nguồn và mức độ xác nhận

- Người dùng học môn Lập trình mạng; topic T03. Nhóm **3 người**; người dùng phụ trách **Phần 1 Tổng quan QUIC và demo**.
- Yêu cầu handoff ban đầu (2026-09-28): gói tài liệu/cấu trúc đưa thẳng vào IDE để Codex triển khai end-to-end đúng kỳ vọng; giữ mọi ý đã thảo luận; hỏi khi thiếu thông tin quan trọng.
- Trong lượt bàn giao ngày 2026-09-28, người dùng chọn **Ubuntu VM** và xác nhận **không có thêm quyết định** trong phần đầu hội thoại bị lược bỏ.
- Go, quic-go, CLI, 6 resource, topology và các API trước đây là đề xuất của assistant. Yêu cầu “cho ra output đúng kỳ vọng theo các ý trên” được hiện thực hóa thành **baseline thiết kế của bộ handoff này**, không ghi sai rằng người dùng đã tự chốt từng thông số.
- Tại handoff 2026-09-28, chưa biết deadline, phiên bản Ubuntu/VMware, cấu hình VM và repo Classroom. Quyết định môi trường cũ nay được D13 thay thế; quan sát máy hiện tại ở VERSIONS. Ubuntu release, toolchain và các thông tin còn thiếu cần xác minh ở P0, không tự bịa.
- Không có transcript nguyên văn đầy đủ của phần bị lược bỏ. Các 31 mục hiện thấy được tổng hợp ở TRACEABILITY; cả 3 tài liệu được giữ nguyên và kiểm checksum. Đây là giới hạn provenance, không phải lý do tự loại requirement hiện có.

## 2. Baseline cần triển khai

| ID | Quyết định | Lý do / trạng thái |
|---|---|---|
| D01 | Raw QUIC qua quic-go, Go; TCP + TLS 1.3 đối chứng | Bám T03; không tự triển khai RFC hoặc HTTP/3 |
| D02 | CLI, terminal, CSV/chart, Wireshark, qlog/qvis | Demo network; GUI chỉ là mở rộng sau |
| D03 | Quyết định gốc 2026-09-28: Ubuntu VM; hai namespace qclient/qserver | Phần môi trường được D13 supersede ngày 2026-09-30; topology giữ nguyên |
| D04 | Một connection mỗi transport, 6 × 1 MiB, chunk 16 KiB | Cùng workload; thể hiện concurrent resources |
| D05 | Một server process, hai listeners TCP/UDP :4433 | Dùng chung resource RAM/certificate |
| D06 | TCP một writer round-robin; QUIC một bidirectional stream/resource | Không giả multiplex bằng truyền tuần tự cả file |
| D07 | QB01 header 24 bytes; codec chung cho cả hai transport | Chốt wire contract và giảm chênh lệch framing |
| D08 | Metric chính ở client, thời gian monotonic | Không trừ clock server với client |
| D09 | 30 lượt đo/transport/scenario, 2 warm-up không tính | Nằm trong khuyến nghị 20–50; warm-up được gắn nhãn |
| D10 | 0-RTT read-only; warm-up ticket; cold/resumed/early riêng | Chứng minh thực sự và xử lý rejection |
| D11 | Không lấy localhost làm performance evidence | Localhost dùng correctness tests |
| D12 | Không đặt tiêu chí QUIC phải nhanh hơn | Kết luận dựa trên số liệu, fail rate và giới hạn |

## 3. Làm rõ/correct các ví dụ trước khi giao AI code

| ID | Điểm trong trao đổi cũ | Hợp đồng sau làm rõ |
|---|---|---|
| C01 | Server egress loss gọi là “data packet loss” | Loss này tác động mọi packet phù hợp hướng/filter, có cả handshake/control; không gọi data-only |
| C02 | Chỉ egress netem trên eth0 | Giữ profile demo egress; benchmark chính receiver ingress qua IFB do TSQ. Không xóa topology hai namespace |
| C03 | Chỉ nhìn thời gian hoàn tất để nói HOL | Cần progress và qlog/PCAP để giải thích; bar chart riêng chỉ là quan sát hiệu năng |
| C04 | Write trước HandshakeComplete “là bằng chứng trực tiếp” | Write chỉ xác nhận API nhận bytes; yêu cầu Used0RTT sau handshake và qlog/capture có packet 0-RTT |
| C05 | DialEarly return gọi connection established | Tách early_ready_ms và handshake_ms; connect_ms không dùng giá trị early-ready |
| C06 | TCP 30 lần rồi QUIC 30 lần | Xen kẽ thứ tự AB/BA có seed, chạy tuần tự từng trial; tránh bias theo thời gian |
| C07 | CSV TTFB có hai cách tính thay thế nhau | Ghi cả first_byte_ms từ t0 và ttfb_request_ms từ đầu gửi request, tên cố định |
| C08 | Header có Offset/Length nhưng chưa có state machine | Chốt big-endian, giới hạn, REQUEST/META/DATA/FIN/ERROR, EOF, timeout ở PROTOCOL |
| C09 | Mỗi QUIC goroutine mở stream → gán ID 0/4/8 giả định | Mở theo resource ID và lưu ID thực; không giả ID thành resource index |
| C10 | Hash ngoài timing từng resource | Đợi tất cả tDone rồi mới hash tất cả buffer, tránh hash R1 ảnh hưởng R2 đang nhận |
| C11 | Rate 20 Mbps nhưng CSV minh họa goodput ~60 Mbps | Loại số minh họa khỏi kết quả; đo thật, kiểm units và sanity bound |
| C12 | Phiên bản/API quic-go ngầm định | Khóa phiên bản ở P0, đọc source/go doc đúng tag; qlog API có thể đổi |
| C13 | Có TLS certificate nhưng chưa nói xác minh | CA/cert local có SAN, RootCAs; không tắt verify mặc định |
| C14 | 0-RTT có cache nhưng không đợi ticket | Quan sát cache Put với timeout; không sleep đoán rằng ticket đã tới |
| C15 | Benchmark runner áp netem nhưng “Go không root” | Shell orchestrator quản lý đặc quyền; Go bench ở namespace client, điều phối các lần đo |
| C16 | Ba docs được gợi ý là đủ | Tách hợp đồng chi tiết theo trách nhiệm để giảm context cần đọc lại; index/trace giữ liên kết |

Những mục C là quyết định kỹ thuật của bản handoff nhằm đóng khoảng trống implementation; không trình bày chúng như lời người dùng nguyên văn.

## 4. Phạm vi mở rộng được giữ lại nhưng chưa làm

Migration/NAT rebinding, nhiều TCP connections, RTT100-loss3, symmetric loss, jitter/reorder, workload khác, dashboard CSV: lưu như backlog, không vô tình biến thành tiêu chí bắt buộc. Lý thuyết migration/flow/congestion/TLS vẫn bắt buộc giải thích. Slides là yêu cầu môn học; bộ coding phải cung cấp outline/evidence phục vụ slides, không tự sinh slide có số liệu giả trước benchmark.

## 5. Quyết định mới sau handoff

Agent thêm ngày, vấn đề, lựa chọn, lý do, requirement ảnh hưởng, file thay đổi và bằng chứng. Không sửa lịch sử nguồn để làm như mọi thứ đã chốt từ trước.

### D13 — 2026-09-30: thay môi trường thực thi của D03

Quyết định hiện hành: Windows 11 host, Ubuntu dưới WSL2 thay Ubuntu VMware VM ban đầu. Người dùng báo đã kiểm chứng netns (tạo/xóa qclient/qserver), veth (tạo/xóa), netem (gắn qdisc 50 ms), IFB (tạo device/UP), act_mirred (load module); tcpdump có sẵn. Quan sát phiên bản/tài nguyên/path cụ thể lưu ở VERSIONS; agent không chạy lại preflight trong migration này. Capability PASS chỉ xác nhận primitives, không tương đương G00/G07/G08 hoặc benchmark hợp lệ.

Chỉ thay execution layer/testbed: giữ Go/quic-go raw QUIC CLI, TCP/TLS một connection multiplex, QUIC một connection/stream mỗi resource, workload deterministic, qclient/qserver/veth/tc/netem, ingress IFB/mirred chính, metric/CSV/schema, benchmark methodology, qlog/PCAP, resumption/0-RTT/rejection, demo và acceptance semantics. Repo trên native Linux filesystem; Remote WSL là cách mở IDE. Requirements ảnh hưởng: môi trường G00, manifest G05/G06, testbed G07/G08 và runbook G12; không giảm gate.

### D14 — 2026-09-30: human-gated mặc định

Thay workflow tự chạy P0→P12 bằng chỉ phase/milestone được user cho phép rõ ràng. Chạy gate đầy đủ, cập nhật TASK, dừng review; chỉ tự nhiều phase/end-to-end khi user yêu cầu rõ ràng. Phiên mới đọc AGENTS/INDEX/TASK và normative docs liên quan phase; originals dùng khi ambiguity/conflict/provenance/final traceability. Giữ source-of-truth discipline và mục tiêu cuối P0–P12; build riêng lẻ không phải gate pass.

D13/D14 được đồng bộ trong AGENTS, start prompt/README/START_HERE, TASK, INDEX, NETWORK, VERSIONS, PLAN, ACCEPTANCE, METRICS, DEMO_SCRIPT, TRACEABILITY và AI_USAGE. Migration chỉ tài liệu; implementation và toolchain pin chưa bắt đầu.

### D15 — 2026-09-30: refinement trong P0 được cho phép

- Pin Go 1.27.1 và quic-go v0.63.0 (minimum Go 1.26.0); cài Go local trong `.tools/`, không sudo build/download, không commit tự động. Đã đối chiếu official metadata, checksum, source đúng tag và compile smoke; xem VERSIONS và evidence/p0.
- Module local `quic-performance-lab` theo PLAN: remote repository không được coi là đã xuất bản Go module. Make giới hạn build parallelism 2 cho tài nguyên hiện có, không phải thông số kiến trúc benchmark.
- Ba mains dùng internal/cli chung; TLS config chung nằm trong internal/tlsconfig/config.go. Không sinh data/hash workload trước P1, không mở socket/transfer hoặc tạo schedule. Thao tác chưa có trả 1, input lỗi trả 2.
- Input bounds bổ sung ở CLI§5 bảo vệ config parser và tránh duration overflow; giữ nguyên workload/scenario chính và schema results. Unknown/duplicate JSON keys bị từ chối. Đây là refinement validation, không đổi thí nghiệm.
- Doctor inventory không root tách khỏi scripts/preflight-network.sh đặc quyền chỉ dùng namespace tạm riêng. Probe không thực hiện G07/G08; lượt agent ban đầu bị chặn ở xác thực sudo. Sau đó người dùng chạy probe thành công lúc 2026-09-30T04:48:25Z; agent đối chiếu log/script và lưu evidence/p0/network-probe.log cùng provenance/hash, đóng G00 PASS. Lịch sử lỗi quyền được giữ nguyên. Các phần độc lập có PASS riêng trong ACCEPTANCE_RESULTS.
- Certificate EC P-256 tự ký dùng làm trust anchor local, SAN cố định theo SPEC, hạn 30 ngày, quyền 0600; tạo lại cần --force rõ ràng. Không commit cert/private key. API qlog và congestion implementation ghi VERSIONS để tránh dùng nhầm API cũ.

### D16 — 2026-09-30: chi tiết QUIC cold P4/G04

- Một process chuẩn bị TCP listener và QUIC UDP listener cùng số port trước readiness; hai listener nhận cùng `*workload.Store` và TLS certificate config. Một semaphore tối đa 8 active connections chia sẻ giữa transport để giữ DEMO_SPEC§3. `--ready-file` công bố bằng hard link atomically trong cùng thư mục, từ chối marker có sẵn; xóa marker do process vừa tạo khi dừng bình thường. Files: `internal/cli/cli.go`, `internal/transport/tcp/server.go`.
- quic-go v0.63.0 chạy QUIC v1 cold qua `Dial`/`Listen`; server nhận tối đa 64 client-initiated bidirectional streams, client từ chối server-initiated bidirectional streams; cả hai từ chối incoming unidirectional streams. Receive credits khởi đầu/tối đa: stream 512 KiB/2 MiB, connection 2 MiB/16 MiB. Đây là sliding flow-control window, không tạo buffer theo tổng credits. Timeout idle handshake đặt bằng một nửa handshake bound cấu hình vì pinned quic-go cho phép tối đa 2× idle timeout; client cũng có dial deadline riêng. Files: `internal/transport/quic/{config,client,server,streams}.go`, `docs/VERSIONS.md`.
- Native `StreamID()` được lưu theo ResourceID; không suy ID từ thứ tự. QUIC request writers chạy sau khi mở đủ N streams; server batch barrier xác nhận REQUEST và send-half EOF trước response, các response workers ghi độc lập. Đây là refinement của PROTOCOL§3/§6 và G04, không triển khai 0-RTT P10, CSV P6 hay benchmark G09. Evidence/trạng thái cuối ở `docs/ACCEPTANCE_RESULTS.md`.

### D17 — 2026-09-30: kết quả cold trial đơn lẻ P5/P6

- `time.Time` được giữ trong client đến khi tính Sub; first DATA byte được ghi ở callback read đầu, không sau nguyên chunk. `total_ms` dừng ở FIN cuối; `elapsed_ms` có thể gồm verify/cleanup. TCP dial success được ghi cả khi TLS handshake fail, mốc handshake thiếu giữ null. Đây là cách áp dụng METRICS§1–2, không đổi công thức.
- Một invocation cold client tạo một thư mục kết quả mới, với raw JSON trước CSV, writer đồng bộ và lỗi flush/close trả nonzero. ID tự sinh có timestamp UTC + random suffix; ID user nhập được giới hạn ký tự path-safe. Không append vào directory có sẵn. Trường 0-RTT/TLS-resumption chưa quan sát ở P10 giữ nullable thay vì bịa false; `attempted_0rtt=false` cho cold. Dữ liệu P6 chỉ là localhost correctness, network_profile `loopback-test`, chưa có manifest full/cohort/benchmark; P9 hoàn thiện phần đó theo METRICS§3–5.

### D18 — 2026-09-30: sửa audit P0–P6

- QUIC resolution dùng context của trial; t0 bắt đầu trước resolve/socket setup như phạm vi TCP Dial. Buffer/config vẫn chuẩn bị trước t0. Setup failure giữ N slots và start/end để ghi failed trial. Không có phép trừ wall clocks hay reset t0.
- Result nội bộ phân biệt checksum chưa kiểm/đúng/sai và lỗi từng resource. Sau khi mọi reader dừng (success hoặc failure), verify các resource đã FIN; tiếp tục kiểm siblings khi một hash sai. Run vẫn fail nếu bất kỳ resource/cleanup lỗi; resource đã verify và cleanup hợp lệ giữ success riêng. TCP cleanup lỗi áp dụng mọi resource trên shared connection; QUIC cleanup được ghi theo worker.
- Validator từ chối INCOMPLETE, kiểm kiểu raw JSON chính xác, stream milestones/order/end và QUIC ID bắt buộc trên successful stream. Không ép first_byte >= request_end. Không đổi schema v1, không triển khai phase mới.

### D19 — 2026-09-30: ownership/lifecycle cho P7

- Topology P7 cố định `qclient`/`qserver`, veth `eth0`, `ifb0` up; marker root-owned ở `/run/quic-performance-lab/topology-v1` gắn UID/GID người gọi sudo với device:inode của hai namespace. `setup` idempotent chỉ khi marker và trạng thái topology khớp; collision không marker bị từ chối, không xóa tên chỉ vì trùng tên. Failure/INT/TERM rollback namespace vừa tạo theo identity; SIGKILL không thể trap và cần kiểm thủ công nếu xảy ra.
- Entry root chỉ dùng cho `ip netns exec`, sau đó `setpriv` hạ về UID/GID thường trước server/client. `teardown` từ chối namespace có PID, thay vì kill process không biết có thuộc lab hay không. Với `make server` foreground ở P7, dừng bằng Ctrl+C trước `make clean-network`; system runner quản lý PID riêng để kiểm interrupt. `make clean-network` chưa là manager cho detached server/capture của các phase sau. Các script không sửa host NIC/routes hoặc tự chạy netem; G07 traffic và host-state vẫn phải kiểm thực trước PASS. Files: `scripts/network/{common,setup,teardown}.sh`, `scripts/run-in-netns.sh`, `Makefile`, `tests/system/run.sh`; requirements NETWORK§2/§6, CLI§3, PLAN P7, ACCEPTANCE G07.

### D20 — 2026-10-01: IFB module tạo thiết bị host trong lần G07 đầu

- User chạy system runner G07 trong Ubuntu WSL2. Collision, rollback, topology, UID drop và ping hai chiều có log thực, nhưng host link comparison FAIL trước transfer: nạp IFB ngầm với mặc định `numifbs=2` tạo `ifb0`/`ifb1` trong `init_net`. Teardown xóa hai namespace, còn IFB host tồn tại. Đây là lỗi của P7, không phải số liệu benchmark hay G07 PASS. Nguồn giải thích driver: [Linux `drivers/net/ifb.c`](https://github.com/torvalds/linux/blob/master/drivers/net/ifb.c); snapshots/log ở `results/p7-g07-JqV32x/host-state/` và `docs/evidence/p7/g07-system.log`.
- Sửa setup nạp `ifb` bằng `modprobe ifb numifbs=0` trước khi tạo IFB namespace và kiểm host link không đổi ngay sau nạp. Không xóa IFB host chung trong teardown. Script recovery một lần chỉ cho phép xóa hai IFB DOWN/noop khi link/address/route hiện tại khớp snapshot lỗi và chỉ hai thiết bị này khác baseline; kiểm IFB identity và host tc filters, recheck trước từng lần xóa, cho phép tiếp tục sau partial delete, rồi đối chiếu lại snapshot baseline. Recovery và G07 rerun cần sudo tương tác của người dùng; static/precheck không thay actual gate. Requirements NETWORK§2/§6, PLAN P7, ACCEPTANCE G07. Files: `scripts/network/{setup,teardown,restore-host-ifb}.sh`, docs/evidence P7.

### D21 — 2026-10-01: impairment và metadata handoff P8

- User xác nhận P7/G07 PASS và cho phép riêng P8/G08. Agent đối chiếu recovery exit0, G07 rerun exit0 cùng bốn actual trials và host comparisons; cập nhật ledger cũ, không ghi đã human-review P8. Không mở P9.
- Dùng Python helper cho privileged kernel observation/config validation, shell giữ ownership lock P7. Script không hardcode scenario numbers; cùng bounds với Go config loader, negative tests bảo vệ duplicate/type/unit/direction/seed. Root state nằm trong thư mục marker P7; output snapshots stdout để user lưu, không root output path tùy ý. Netem1:/ingressffff:/flowerpref10 reserved; foreign qdisc/filter từ chối. Clear giữ namespaces và offloads OFF đến teardown. Applied state chỉ publish sau actual qdisc/filter/offload verification; tc errors rollback/nonzero.
- Client P8 thêm --network-state, recent<=5 phút/đúng qclient identity, nhận scenario/profile/numeric/seed fields; raw/CSV v1 giữ metadata cả failure. P8 trials gắn evidence/evidence, tránh nhập vào main cohort; schedule/full manifest/performance labeling thuộc P9. Snapshot là observation của wrapper, không locking/continuous guarantee trong transfer; wrapper phải kiểm trước/sau và reset khi idle.
- Seed requested phải kernel/tc report đúng; không silently fallback. Unsupported có thể chọn explicit --seed=none với null/disabled-explicitly và limitation. Downstream tác động tất cả lab IPv4 theo hướng, không DATA-only, drops không đồng nghĩa empirical random loss. G08 runner giữ cả success/failure/missing records trong summary; kiểm loss bulk có observed downstream drops nhưng không equate mọi drop với configured random loss. G08 network còn BLOCKED tại sudo tương tác; build/unit/race/regression không thay gate. Files scripts/network/{netem,clear-netem,inspect,state}, config network reader, CLI/metrics metadata, tests/system G08. Requirements NETWORK§3–6, CLI§1–3, METRICS§3–5, PLAN P8, ACCEPTANCE G08, TRACEABILITY rows6/7/21/24.

### D22 — 2026-10-01: default IFB qdisc trong G08

- Actual G08 tại results/p8-g08-Dw8rGB FAIL: root fq_codel handle0: trên IFB bị guard nhận nhầm foreign; rollback/clear cũng bị chặn. Topology teardown thành công, host final unchanged; zero probes/trials.
- Nhận kernel baseline root handle0: noqueue, hoặc fq_codel chỉ trên IFB owned; giữ nguyên baseline qua clear. Dùng cùng predicate trong apply/inspect, checker cleanup đối chiếu cùng policy. Foreign handles/placement vẫn bị từ chối trước deletion. Regression 9 tests PASS; chưa actual rerun, không đổi gate sang PASS. Requirements NETWORK§3–6, PLAN P8, ACCEPTANCE G08.

- Đóng evidence D22 sau user rerun UTC02:57:20Z: actual G08 PASS main0/cleanup0, expected SIGINT child130/cleanup0; review/hash tại evidence/p8/g08-rerun-review.json, results/p8-g08-96nOtS/ và p8-g08-qOYl2H/. Không đổi phạm vi/decision, không P9 hoặc claim human code review.

### D23 — 2026-10-01: runner/cohort refinement P9

- User xác nhận G08 PASS và cho phép riêng P9/G09, dừng review sau gate. Schedule v1 nhúng validated workload/scenario, exact hashes/CA/endpoint/timeout; entries hash-bound, tối đa4096/8MiB. SplitMix64 v1 seed/order được định nghĩa trong code, seeded starting order rồi alternating AB/BA; netem seed unique mỗi pair và reset trước từng transport. Không gọi cùng seed là identical loss trace. Overrides/subsets là exploratory; default main giữ240 measured+16 warmup.
- Cùng RunCold dispatch cho client/bench, fresh connection/cache. Main warmup/measured metadata chỉ từ immutable entry + matching actual recent snapshot/namespace, trace performance. Direct bench loopback-test không gán configured impairment. Sidecar actual TLS/cipher/ALPN/QUIC/state/socket buffers lấy trong cleanup sau FIN, không đổi schema/timing formulas; server per-socket buffers chưa lấy thì manifest ghi unknown/reason.
- Shell đặc quyền chỉ topology/qdisc/namespace entry/managed process lifecycle. Checks/probes/data/analysis và Go đều UID thường. Watchdog trial timeout+15s, TERM rồi grace5s; lỗi transfer có raw vẫn giữ, chỉ tiếp tục sau full server bound/queue drain và quiet path; lỗi infra/missing/incomplete thì dừng. Cleanup giữ original signal/nonzero và host snapshots; không kill process của người dùng khác.
- Single-owner merge một lần, source shards giữ/hash, invalid cohort bị reject, incomplete/exit/network-invalid output bị fail trong aggregate. `n_attempted` là scheduled denominator; `n_invoked` riêng. Missing rows là required failure representation, không đo giả: N rows, latency/goodput/hash null; elapsed=0 sentinel do schema v1 non-nullable, `elapsed_observed=false` ở merge sources. Code not_started/interrupted/missing_shard/timeout phân biệt journal/exit; original raw không sửa. Stats chỉ successful measured, failures luôn báo, p95 nearest-rank/sample n−1; resource ID distributions không pooling correlated siblings.
- Analysis pin đầy đủ packages tại requirements.txt, Python3.14.4/Linux actual install user-owned `.tools/analysis`, Matplotlib3.10.8 Agg/SVG/PNG. [Official version documentation](https://matplotlib.org/3.10.8/index.html), [release files/Python compatibility](https://pypi.org/project/matplotlib/3.10.8/). Không tải/cài trong benchmark/live, không sửa Go/quic-go/config/result schema/originals.
- Actual G09 attempt exit1 trước runner do `sudo: interactive authentication is required`; software/unit/race/localhost và genuine process-kill failure tests không thay ingress main cohort. G09 overall BLOCKED, P10–P12 NOT_RUN; runbook/manual commands ở evidence/p9. Requirements NETWORK§5–7, CLI bench contract, METRICS§3–7, PLAN P9/G09, ACCEPTANCE G09, TRACEABILITY rows1/19/21–24/29.


Closure actual P9/G09: User full G09 rerun 2026-10-01 tại results/p9-g09-8dFdkj PASS (g09_exit=0): main256 invoked/256 success/0 failure/0 missing, 240 measured+16 warmup/1536 resource rows; controlled SIGINT child130/cleanup0. Agent read-only audit/hash tại docs/evidence/p9/g09-rerun-review.json; không tự nhận chạy sudo. Dừng human review P9, không P10. Interactive terminal Ctrl+C qua tee từng exit141/cleanup1 vẫn là issue riêng, không được coi đã sửa bởi controlled child PASS.
