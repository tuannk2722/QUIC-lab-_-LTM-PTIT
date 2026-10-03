# P11/G11 — actual PASS, hồ sơ đã đóng

User chạy `bash scripts/run-g11-review.sh` trong Ubuntu WSL2 và xác nhận P11/G11 PASS; log [g11-user-run.AGayVd.log](g11-user-run.AGayVd.log) có `g11_exit=0`. Actual root: [results/p11-g11-6a8cc99602b7](../../../results/p11-g11-6a8cc99602b7/). Agent audit read-only/copy checker, không tự nhận chạy privileged rerun hoặc human code review. User authorize riêng P12/G12; [P12 runbook](../p12/README.md), entry `bash scripts/run-g12-review.sh`. Historical FAIL/BLOCKED giữ nguyên bên dưới.

| Acceptance | Status | Actual evidence |
|---|---|---|
| G11-qlog/progress/viewer | PASS actual |30 exact quic-12 qlogs,7683 target payload points,23 HTML/PNG/SVG viewers; ODCID/endpoint/native stream/role correlation |
| G11-actual23/bytes/FIN/hash | PASS |23 planned/invoked/success,0failed,123 resource rows/hash checks; all attempts retained |
| G11-PCAP/UDP/lifecycle | PASS |46 paired capture dirs,282370 packet records,10..7241 per capture,complete/drop0/cleanup0; tshark4.6.4 decode |
| G11-early REQUEST | PASS |handshake_early actual DidResume/Used0RTT=true,rejected=false,fallback0; both captures frame14/PN0/native stream0/resource1/exact32-byte QB01 REQUEST |
| G11-HOL causal trace | PASS |First qualifying retained pair loss_0_tcp/loss_0_quic; ACK/SACK gap+retransmission+app stall and lostPN/ranges+sibling progress+recoveryPN |
| G11-IFB/RTT/UID/idle/cleanup | PASS |Baseline medians0.2925/0.2495ms; rtt50-loss0 medians50.6/50.6ms; verified ingress IFB/seed/offload/counters/last quiet,UID1000,cleanup0/host unchanged |
| G11 overall | PASS |Original [g11-check.json](../../../results/p11-g11-6a8cc99602b7/g11-check.json) qlog/progress/UDP/early/HOL PASS,full_demo_complete=true; [audit](g11-rerun-review.json), [copy checker log](g11-rerun-check.log) |
| G12 | IN_PROGRESS |Authorized separately; software/docs do not pass actual Make demos and5–7min rehearsal |

[Read-only closure audit](g11-rerun-review.json) records125 as-run source hashes,45 build inputs bound to archived sources and receipt/manifest equality. Later authorized P12 changes are disclosed; no source hash/raw/receipt rewrite. Independent [public archive](g11-user-run-artifacts.tar.gz) has662 byte-verified members and SHA256 `a237a68091d2122bd6648662293aed5f2ef4ec7949beff24ea71decdaca6bd65`. It contains raw/CSV/manifests/host/network/probes/receipts/qlog/capture status/notes/viewers; keylogs/PCAP/large decoded files remain in actual local root. This archive is a review bundle, not a complete decrypted-capture reproduction input.

Original checker inventory797/798 public files matches. The sole exception is `logs/check.log`: the checker hashes its redirected log while still open, before printing summary, so original receipt records SHA256(empty). Completed log381 bytes has independently recorded SHA256 `98c154b39bd19eaecee71b5eab8b3852b4515c57be90eac313e3a5b830f06184`; audit/archive verify completed bytes. The exception is explicit; original files and receipt were not altered. Copy replay log PASS; the audit receipt may separately show replay progress until that independent audit finalization is recorded.

Early packet and API: request_end1.945624ms, observed handshake56.605283ms; these timestamps support the decoded packet proof, not replace it. Exact [precheck](../../../results/p11-g11-6a8cc99602b7/early-packet-check.json) contains the32-byte REQUEST witness at source port34352→4433 in both captures. Qlog client-sent/server-received PN0/stream0/offset0/length32 matches target connection.

Representative [annotated notes](../../../results/p11-g11-6a8cc99602b7/evidence-notes.md): TCP gap sequence3187438027, ACK237/SACK[3187439475,3187440923],original frame228,later229,retry248,advancing ACK253 and app stall. QUIC lostPN25 carries stream20/resource6 range1345+1257; later offset2602 arrives inPN30, sibling resource5 delivers16384 payload bytes before missing-range recovery inPN50. All ten random loss pairs are retained; selection is first qualifying pair, not a sample chosen because QUIC wins.

Instrumentation is evidence mode and excluded from actual performance cohorts P9/P10. Eth0 capture tap can precede IFB drops; TCP kernel ACK/SACK and receiver qlog corroborate reception. HOL uses same-host wall alignment3ms and validated16KiB payload sampling; packets can contain multiple streams and shared congestion/flow control still affects siblings. HTML generated offline, browser rendering unverified; PNG/SVG rendering available. Windows11 is user-reported D13; WSL app version was not queried. Historical P9 interactive Ctrl+C through tee limitation is not closed by G11 cleanup success.

For a new independent G11 reproduction from native Ubuntu WSL2 repo root with idle/absent topology and prepared dependencies:

```bash
bash scripts/run-g11-review.sh
```

This reruns full23 actual evidence trials and prints a new result/log path; it is not required merely to close this completed gate. Do not commit or upload keylogs/PCAP by default. P12 demos use accepted evidence as labelled pre-recorded backup when one live loss sample is inconclusive.

## Checkpoints lịch sử trước closure — không là status hiện hành

The following snapshot is preserved as historical explanation of D26–D29 fixes and prior runs. Its FAIL/BLOCKED/NOT_RUN, “rerun pending” and “P12 not authorized” statements apply only to those earlier checkpoints. Current status is the PASS table above.

<details>
<summary>Đọc snapshot P11 trước actual rerun PASS</summary>

# P11/G11 — early keylog fix PASS; full actual rerun pending

Latest D29: user-run `results/p11-g11-1200e3df1cf2` FAIL trước setup/trial vì reset-env PATH thiếu /usr/sbin, không resolve sysctl.23 planned/0 invoked,cleanup0 và host unchanged. **Đã sửa PATH** ở G11/capture/sinks/namespace entry, thêm owner-tool preflight;9 lifecycle/environment tests PASS và exact runtime metadata command đã chạy thật bằng UID1000/real sysctl. [Log user](g11-user-run.Jbm1be.log), [tests](g11-path-lifecycle.log), [audit/runtime/hashes](g11-path-review.json). Không cần cài package hoặc sửa PATH thủ công; chạy lại cùng một command bên dưới.14 failed-run artifacts giữ nguyên; không coi metadata-only check là full gate PASS.

Current D28 export: missing early-secret export đã sửa bằng hash-checked Go1.27.1 build-only TLS overlay; không đổi Go/quic-go pins hoặc custom crypto. Actual client/server early secrets matches, cold/resumed không log early, rejected chỉ client log, writer errors propagated; full Go/race PASS. Historical actual5/23 và latest D29 preflight0/23 FAIL giữ nguyên; new full gate cần interactive sudo. Không tuyên bố P11 hoàn tất trước actual gate.

**Chạy trong terminal Ubuntu WSL2 bằng user thường:**

```bash
bash scripts/run-g11-review.sh
```

Script tự make build, sudo hỏi mật khẩu, chạy đủ23 trials và in `g11_exit`/`log`. G11 kiểm decrypted early REQUEST ngay sau3 handshake trials trước20 bulk, rồi full checker sau cleanup. Đây là lệnh cần chạy hiện tại; không cần cài thêm package hoặc lặp8 tests.

## D28 — early-secret export và kiểm chứng hiện hành

- [Generator](../../../scripts/tls_keylog_overlay.py) kiểm Go1.27.1 và exact SHA256 hai upstream files; build-only [patch](g11-early-overlay.patch) thêm existing writeKeyLog calls, không derive secret, không sửa installed GOROOT/module cache. Local TLS observability patch được ghi rõ trong D28/VERSIONS; binaries không dùng stdlib nguyên bản.
- [Build final](g11-early-build-final.log), [full suite](g11-early-suite.log), [full race](g11-early-race.log), [6 early subcases](g11-early-detail.log), [4 provenance checks](g11-early-provenance.log), [8 lifecycle](g11-early-lifecycle.log), [6 detector checks](g11-early-detectors.log): exit0. Build receipt bind generator và original/overlay hashes. Sandbox socket-denied attempts giữ riêng, corrected runs dùng sockets UID1000 ngoài sandbox.
- New actual localhost root `results/p11-software-xzfxm1sf`:6 trials,5 success+1 expected wrong-hostname TLS failure; [driver](g11-early-software.log), [software checker](g11-early-software-check.log), [secret labels/API/qlog review](g11-early-secret-review.json). Client/server early secret values chỉ kiểm trong local process; review không xuất secret bytes. Qlog target PN0/stream0/offset0/length32 matches actual Used0RTT. PCAP REQUEST/IFB/HOL vẫn cần actual capture.
- [Latest agent full-gate attempt](g11-early-system-attempt.log): exit1 `sudo: interactive authentication is required` trước runner; không automatic approval rejection hoặc topology change. Entry script trên cần terminal tương tác của người dùng. P12 chưa authorize.
- As-run source receipts giữ nguyên; software snapshot được tạo trước refactor early precheck/current provenance-test additions. Current file differences được khai báo trong status, không rewrite source hashes hoặc gán code mới cho lịch sử.

## Checkpoint D27 — lịch sử trước early-secret fix

User authorize riêng P11/G11 ngày2026-10-02, sau đó authorize sửa shutdown/environment/capture và format TASK. Latest actual user-run `results/p11-g11-3344e60b5868` **FAIL**:5/23 successful trials, shutdown runner exit1/cleanup0/host unchanged; checker chưa chạy. [User log](g11-user-run.DC0kWH.log), [read-only audit/hashes](g11-fix-user-review.json). Fixes software PASS; agent thử full gate bản sửa vẫn sudo interactive authentication exit1 trước runner ([attempt](g11-fix-system-attempt.log)). Không automatic approval rejection; bản sửa chưa actual network-tested. Dừng human review P11, không commit/P12.

## Bản sửa D27 và blocker còn lại

- Shared child wait xử lý race giữa liveness check và signal; reaped exit status mới quyết định PASS/FAIL. Child error hoặc forced KILL vẫn fail, chỉ signal owned PID.
- G11/capture helpers và namespace entry dùng `setpriv --reset-env`; HOME/USER/LOGNAME/PATH về owner, root XDG/Wireshark settings bị loại. G11 truyền lại explicit NETEM_SEED để giữ seed-null choice.
- tcpdump `--immediate-mode -U`, stop chờ reader200ms ngoài timing rồi SIGUSR2 flush/SIGINT; sinks join EOF/fsync. PCAP count/framing/tcpdump footer/drop được kiểm, empty/truncated/count mismatch không còn cleanup PASS. Header-only PCAP cũ không thể phục hồi bằng bản sửa.
- [8 lifecycle/environment/PCAP/checker regressions](g11-fix-lifecycle-final.log), [network regressions](g11-fix-network.log), [final build receipt](g11-fix-build-final.log) PASS. Không đổi Go code, không lặp Go suite/race đã PASS; actual capture drain mới vẫn chờ terminal rerun.

**Early-keylog blocker mới xác minh:** actual early-server PCAP có packet0RTT nhưng Wireshark báo decryption failed. Read-only decoder audit đọc26 packet rows/3 decrypted STREAM frames (prior/1RTT), full early REQUEST vẫn INCONCLUSIVE; [log](g11-fix-decoder-actual.log), local derived root `results/p11-fix-audit-10ea741bba`. Client/server keylogs chỉ có handshake và1RTT labels, thiếu `CLIENT_EARLY_TRAFFIC_SECRET` (audit lưu labels, không secret values).

Pinned [Go1.27.1 client early path](https://github.com/golang/go/blob/go1.27.1/src/crypto/tls/handshake_client.go) và [server early path](https://github.com/golang/go/blob/go1.27.1/src/crypto/tls/handshake_server_tls13.go) cấp early secret cho QUIC events nhưng không gọi KeyLogWriter ở path đó; public qlog key event v0.63.0 không export secret bytes. Đây là blocker lịch sử D27, đã xử lý export trong D28 ở trên. Original PCAP/keylogs thiếu secret không được sửa hoặc tạo secret bù; cần lượt capture mới để kiểm full REQUEST proof.

TASK hiện là checkpoint ngắn; bản cũ giữ nguyên ở [.codex/history](../../../.codex/history/TASK-2026-10-02-before-p11-fixes.md). Artifact user-run/as-run receipts giữ nguyên; fixes không được gán provenance vào lần chạy cũ.

P10 closure: actual user-run `results/p10-g10-cR1oR9`,96 target successes/90 measured+6 warmups/64 ticket warmups, cold/resumed/early30 API-qualified mỗi mode; cleanup0. Agent audit trên copy và archive1836 files byte-verified tại [P10 review](../p10/g10-rerun-review.json). Blocked logs P10 cũ giữ nguyên; không tự nhận agent chạy sudo hoặc human code approval.

## Scope và evidence thật

Client/server optional exact-tag qlog JSON-SEQ/quic-12 và keylog0600/thread-safe/new-file-only; flush/error propagation sau shutdown. Client `--progress` thu private bounded payload points/resource/attempt sau validated DATA,16KiB thresholds/chunk cuối, flush sau timing. Existing first-byte hook, QB01, stream independence/TCP writer, schema/config/Go pins giữ nguyên. Any trace bật phase/trace_mode=evidence; performance bench từ chối traces.

Mapping dùng ODCID + actual connection_started endpoint, client run_id và role ticket/target; không suy filename order. Offline viewer giữ JSON-SEQ nguyên bản, có event/packet/stream filter và progress, standalone PNG/SVG. PNG đã opened/visually reviewed; HTML generated nhưng chưa browser-render-test, không claim qvis compatibility.

Full driver `tests/system/g11.sh`: plan23 trước setup (3 handshake modes/rtt50-loss0 +10 cặp bulk TCP/QUIC/rtt50-loss3), all attempts/failures/invocation starts/ends/raw giữ lại, alternating order và changing pair seeds. Namespace/capture wrappers sở hữu PID cụ thể và bounded cleanup; apps/analysis/file sinks UID thường. Capture qclient/qserver eth0 paired, tcpdump readiness/log/drop/status; eth0 tap có thể trước IFB drop. TCP kernel ACK/SACK và client qlog receive corroborate reception. Checker/decode logs giữ artifact độc lập terminal pipe; không đóng issue interactive Ctrl+C lịch sử P9 bằng software checks.

Decoder tshark4.6.4 được tải/extract local từ Ubuntu packages/exact hashes, không hệ thống/root install ([receipt](g11-decoder-receipt.json), [version](g11-decoder-version.log), [reproduction](g11-decoder-reproduce.log)). Source API theo pinned quic-go v0.63.0 `NewConnectionFileSeq`; [Tshark manual](https://www.wireshark.org/docs/man-pages/tshark.html) và [QUIC field reference](https://www.wireshark.org/docs/dfref/q/quic.html) hỗ trợ offline PDML adapter. Actual partial historical PCAP decoded UDP/1RTT; fresh early packet/full23 còn pending.

## Acceptance

| ID / subcase | Status | Evidence |
|---|---|---|
| G11-build/suite | PASS | [build](g11-build-final.log), [current full suite](g11-suite-current.log), exit0 |
| G11-race/concurrency | PASS | [full race](g11-race.log), [detailed rejection race](g11-detail-integration.log), [sinks/collector race](g11-detail-unit.log), [progress writer guard race](g11-progress-writer-tests.log) |
| G11-qlog/parse/correlation/flush | PASS, localhost |12 actual connection traces,6 client+6 server, parsed and ODCID/endpoints bound; [review](software-review.json) |
| G11-progress/attempts/failure rows | PASS, localhost |771 target payload points; bulk384 points/transport, each6×1MiB hashes; handshake3 points; genuine wrong-hostname TLS failure keeps6 rows/header-only progress; rejection six workers/32769 bytes each/3 points each, attempt0 has no discarded payload |
| G11-viewer | PASS, local PNG/SVG | [real sample root](../../../results/p11-software-qpkpmo80/viewers/), units/run_id/schema and caveat opened; HTML browser status unverified |
| G11-early qlog/API corroboration | PASS, partial | Actual DidResume/Used0RTT and request enqueue before observed handshake; target0RTT PN0/native stream0/offset0/length32 at client+server. Qlog lacks payload content; **not full packet REQUEST proof** |
| G11-detector/regressions | PASS, software | [six evidence tests](g11-evidence-tests.log), [analysis regressions](g11-analysis-final.log), [network regressions](g11-network-regression.log); synthetic unit fixtures are tests, not measured evidence |
| G11-PCAP/QUIC UDP | PASS, partial historical decoder only | Actual early-server PCAP decoded26 rows/3 STREAM frames; not full gate |
| G11-early-secret export | PASS actual localhost | [review](g11-early-secret-review.json), [6 subcases](g11-early-detail.log); existing early secret log, accepted matches/rejection/error handling |
| G11-decrypted early REQUEST | BLOCKED actual rerun | Historical PCAP lacks early secret; fresh capture required after D28 export fix |
| G11-capture/actual23/IFB/RTT/cleanup | FAIL, latest user-run; patched rerun BLOCKED | Five successful transfers/cleanup0/host unchanged;3 empty short PCAP and shutdown failure; remaining18 trials absent |
| G11-fix regressions | PASS, software | [analysis](g11-fix-analysis.log), [final lifecycle/checker8](g11-fix-lifecycle-final.log), [network](g11-fix-network.log), [static](g11-fix-static.json); actual new capture behavior not yet verified |
| G11-HOL causal trace | NOT_RUN full checker | Only first impaired pair transferred; no chosen/validated representative; insufficient causality remains INCONCLUSIVE |
| G11 overall | IN_PROGRESS; latest actual FAIL, rerun BLOCKED at sudo | [status](g11-status.json); full23 actual still required |
| G12 | NOT_RUN | Not authorized |

Original final software source: `results/p11-software-qpkpmo80/`; six trials,5success+1 genuine expected TLS failure,12 qlogs,771 target points and2 ticket points riêng. [Driver log](g11-software-final.log), [checker log](g11-software-check-final.log), [review/hashes](software-review.json), [public archive94 files](software-artifacts.tar.gz) byte-verified. Archive excludes every `.keylog`; retained qlogs/raw/progress/attempts/receipt/logs/viewers/notes are real. Checker passed on a copy without secrets. Initial software run `results/p11-software-53py2hwj`/logs kept separately.

As-run receipt/source inventory giữ nguyên. Progress trace-mode guard và capture/checker refinements sau software run được kê trong source_changed_since_run, không viết provenance giả. Final guard checked full suite/unit/race; current checker reopens actual traces. Privileged capture/checker branch vẫn chưa actual-tested. Sandbox socket denial [history](g11-suite-first.log) và indentation-edit failure [history](g11-checker-edit-error.log) đã corrected, final checks PASS. [Read-only host check](g11-host-readonly.json) thấy no lab namespace/marker/managed apps; đây không phải actual interrupt cleanup gate.

## Chạy lại full G11 trong terminal Ubuntu WSL2

Từ native Linux repo root, topology/server cũ absent; build/dependencies/cert bằng user trước sudo. Existing cert chỉ tạo lại nếu thiếu; không overwrite key đang dùng. Analysis/decoder và system ripgrep đã có, không cần cài lại. D28 early export đã verified; dùng `bash scripts/run-g11-review.sh` ở trên. Các lệnh dưới là equivalent manual sequence:

```bash
make build
# make analysis-deps  # chỉ nếu thiếu
# make decoder-deps   # chỉ nếu thiếu
# make certs  # chỉ nếu certs/server.crt/key chưa có
sudo -v
g11_log=$(mktemp docs/evidence/p11/g11-user-run.XXXXXX.log)
set -o pipefail
sudo bash tests/system/run.sh --gate G11 2>&1 | tee "$g11_log"
g11_status=${PIPESTATUS[0]}
printf 'g11_exit=%s\n' "$g11_status" | tee -a "$g11_log"
printf 'log=%s\n' "$g11_log"
```

`make decoder-deps` kiểm exact packages/hash ở `analysis/decoder-packages.json`, extract `.tools/tshark`; không sudo pip/apt install. System tshark nếu có được ưu tiên và version ghi manifest. Nếu archived Ubuntu package version không còn available, report/fix preparation rõ ràng; không silently chọn floating decoder. `NETEM_SEED=none` chỉ dùng khi chủ động chọn seed-null limitation, qua `sudo env NETEM_SEED=none bash tests/system/run.sh --gate G11` và log riêng.

Review printed `gate_root=results/p11-g11-*`, logs/check.log và g11-check.json:23 planned/invoked/failure denominator, four12-sample probes, before/after/last quiet snapshots/counters/seed/config/UID,46 paired capture dirs/drop0/cleanup0, target/ticket qlog map và32-byte decrypted REQUEST witness, viewer/notes/all attempts, host unchanged/cleanup0. Sidecars/keylogs local cần giữ để rerun decoder; không upload public hoặc commit secrets. Captured artifacts có thể lớn; raw results không bị xóa.

Gate tools/UDP/early có thể PASS và HOL **INCONCLUSIVE** nếu10 pairs không có witnesses đủ. Trong trường hợp đó g11-check.json ghi full_demo_complete=false, không claim full demo proof. User review annotation PN/frame/stream/range/ACK/SACK + progress trước đóng HOL. Không cần/không được thay random loss bằng sleep hoặc targeted drop chưa có spec.

Software-only reproduction, không root/IFB/PCAP:

```bash
python3 tests/system/run_g11_software.py
python3 tests/system/check_g11.py results/p11-software-<printed-id> --software
```

## Điểm cần review

- Qlog/keylog ownership,0600/exclusive files, shared TLS clone writers, flush/error propagation và observed actual state; correlation by ODCID/endpoints/role.
- Progress allocation cap/threshold resolution, per-worker slice, failure/rejected/replayed attempt separation, post-timing writes và no performance pooling.
- Privilege/PID/capture readiness/EOF/deadline/INT/TERM, last quiet before reset, host ownership; actual branch remains unverified until manual gate.
- Decoder coalesced headers và exact QB01/native stream mapping; causal TCP ACK/SACK/retransmission and QUIC missing range/sibling/recovery witnesses.3ms same-host correlation margin và16KiB sampling có thể bỏ sót trace; không dùng wall clocks làm latency metric.
- Instrumentation overhead/shared WSL2 CPU, shared congestion/flow control và nhiều streams trong cùng lost packet. Qlog packet_lost là detection event, có thể spurious; localhost loss events/progress không prove configured loss/HOL. P12 demo/rehearsal/report packaging chưa làm.

</details>
