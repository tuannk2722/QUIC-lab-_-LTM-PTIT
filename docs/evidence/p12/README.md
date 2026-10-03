# P12/G12 — reproduction và rehearsal

2026-10-03 (Asia/Saigon). **P0–P12/G00–G12 PASS.** User chạy full entry tại `results/p12-g12-51c13b94f99b`, `g12_exit=0`, full checkerPASS:14softwaresteps/610sourcefiles,8/8demo successes,live360.000793725s,baseline preparation177.218538684s riêng trước live,UDP/early/liveHOL/cleanupPASS. [Closure audit](g12-rerun-review.json), [user log](g12-user-run.RUbjTU.log), [current review](g12-review.json). Previous423sFAIL và sudoBLOCKED giữ nguyên ở history bên dưới. Human code/oral/browser/video/slides review pending.

## Lệnh chạy đầy đủ

Từ repository native Ubuntu WSL2 `/home/...`, bằng UID thường, dependencies chuẩn bị theo [README](../../../README.md), dừng foreground lab server/benchmark trước:

```bash
bash scripts/run-g12-review.sh
```

`make gate-g12` gọi cùng entry. Wrapper in `gate_root`, `log`, `g12_exit` hoặc failure-stage exit. Password chỉ nhập vào terminal Ubuntu. Mỗi lượt tạo NEW root/fresh candidate; không rerun patched driver trên old source receipt hoặc sửa timing cũ thành PASS.

Gate clone local HEAD detached, overlay exact tracked+nonignored current candidate, own .git/base SHA và source hashes, không commit/push; không inherited bin/certs/results/build cache. Prepared pinned Go1.27.1/modules/analysis/tshark caches được disclose và dùng offline. Không claim clean OS bootstrap hoặc new remote committed revision. Software chạy module verification/build/cert/doctor/full Go/analysis/network/demo/G12 tests, actual localhost6 attempts (5success+1expected TLS failure), validator, actual `make analyze` từ archived G09 vào NEW derived tree và1028 canonical hashes unchanged. Benchmark/handshake public target dry-run chỉ kiểm contract; actual main performance acceptance từ G09/G10, không chạy lại240-run suite trong live.

## D31: preparation và live clock

Sau software PASS và interactive sudo:

1. **Preparation:** chạy thật `make demo-baseline` (TCP+QUIC bulk no-loss) với full probes/paired capture/proof/cleanup. `preparation.json` ghi actual argv/exit/start/end/duration/log hash; lỗi thì dừng trước live. Baseline luôn mandatory.
2. **Live:** bắt đầu đồng hồ mới, theo DEMO_SPEC A→C→B: `make demo-quic-basic`, `make demo-loss`, `make demo-0rtt`, `make cleanup`; topology/UDP/loss/early/summary/limitations cùng actual command duration được tính vào live. Target360s, acceptance vẫn **300–420s**. `rehearsal.json` schema2 bind preparation SHA/owner/offline/chronology; không cắt commands còn chạy, không nới giới hạn nếu chậm.
3. **Final G12:** independent checker kiểm đúng current source/fresh provenance/full software/prior overall G00–G11 evidence/original hashes; đủ **bốn actual demo targets**, raw/qlog/progress/PCAP/network/probes/UID/failure denominator/cleanup; chuẩn bị trước live, exact Make argv/output/log hashes và actual5–7min. Namespace/host sạch.

D30 đã đưa thêm baseline97.220724s vào live, trái thứ tự A→C→B của DEMO_SPEC và gây user-run423s FAIL. [D31](../../CONTEXT_AND_DECISIONS.md) ghi refinement; baseline acceptance được chuẩn bị trước buổi live, không bỏ test/probe/trial/proof. Synthetic regression dùng observed durations chỉ là unit-test inputs, không phải actual patched rehearsal. Human oral delivery/code ownership/browser/video/slides chưa được chứng nhận.

## Actual G12 PASS — 2026-10-03

| Stage | Actual duration (s) | Acceptance |
|---|---:|---|
| Baseline preparation |177.218539|PASS;2TCP/QUIC trials;separate before live|
| Live basic |51.114730|PASS;QUIC/UDP decode|
| Live loss |160.604076|PASS;2trials/live causal TCP+QUIC HOL|
| Live0rtt |50.746042|PASS;cold/resumed/early;actual accepted REQUEST|
| Live cleanup |0.088001|PASS|
| Live total including explanations/waits |360.000793725|PASS;within300–420s|

Full actual checker scope=`full G12`,status=PASS,full_gate=true; software/package14/14steps exit0,UID1000,fresh610sourcehashes/own.git/base8721f6346bf62cdab9aa653c9105e1ad3ed9516e,empty inherited bin/certs/results/buildcache.12demo+24G12 regressions and Go/analysis/network suites PASS; actual localhost6 attempts at `fresh/results/p11-software-ltrjdy0h` (5success+1expectedwrong-hostnameTLSfailure),1028analysis canonicalhashes unchanged; three originalreference hashes unchanged. Prepared pinned offline caches reused and candidate not newly committed.

All-four-demo8planned/invoked/success,0failed/missing;pairedPCAP/qlog/progress/RTT/IFB/UID/counter/idle evidence verified;alloriginal/cleanup exits0,host link/address/route byte-identical before/active/final. Actual privileged G12 final wrapper confirmed namespace/marker absence as-run; closure audit does not rerun sudo/network. Read-only replay uses as-run fresh verifier and binds completedchecklog SHA/fullchecker summaries/preparation/live logs, source/fresh/currentimplementation and everycanonical hash; original artifacts remain unchanged. No need rerun accepted G12 just to answer PASS.

Early `handshake_early`:DidResume/Used0RTT=true,fallback0;both capture frame14,PN0,nativestream0/resource1 contain exact32-byteQB01REQUEST. Live HOL: TCP gap1259812609,ACK244/SACKlater235,retry254/advancingACK259;QUIC lostPN155,stream12/resource4,gap28031/later29286(PN161),distinctsiblingprogress before recoveryPN176. One instrumented sample demonstrates mechanism; not a main performance cohort or unconditionalQUICsuperiority claim.

[Closure audit](g12-rerun-review.json), [archive receipt](g12-rerun-archive.json), [public actual bundle](g12-user-run-artifacts.tar.gz):353byte-verified members,SHA8d053bede0326a95977c20b2f3d730d936c4ff5028d82b2cbc196097e3379827. [Full checker](../../../results/p12-g12-51c13b94f99b/g12-check.json), [live receipt](../../../results/p12-g12-51c13b94f99b/rehearsal.json), [preparation](../../../results/p12-g12-51c13b94f99b/preparation.json). PCAP/keylogs/large decoderlocal, excluded from public archive; full replay needs originals. HistoricalFAIL/BLOCKED archives/receipts unchanged. [Before closure review](g12-before-closure-review.json).

Review next: code ownership/10Q&A,spoken delivery and presentation assets,preparedoffline provenance/candidateoverlay,conservativeearly/HOLcriteria and lifecycle/cleanup. TimedterminalPASS does not certify browser/video/decksubmission or human codeapproval. StopP12 review,no commit/upload/nextphase.

## Historical actual FAIL — superseded by user51c13 PASS

| Step | Duration thực tế (s) | Exit/proof |
|---|---:|---|
| basic |57.037136|0;1/1success,UDP decode PASS|
| baseline |97.220724|0;2/2success|
| loss |190.862634|0;2/2success,live TCP/QUIC causal HOL PASS|
| 0rtt |52.758191|0;3/3success,actual early REQUEST PASS|
| cleanup |0.073762|0|
| Walkthrough total |423.01996559|FAIL>420s; final system checker NOT_RUN|

Read-only replay từ **as-run fresh verifier** đã kiểm mọi demo artifact inventory/raw/CSV/progress/qlog/paired capture/decoder/network/RTT/idle chronology và proof; không rewrite originals.8 planned/invoked/success,0failure/missing. Mỗi demo original/cleanup exit0, host link/address/route byte-identical before/active/final. Không pooling instrumented samples vào performance cohort. User entry log [g12-user-run.9vwiHk.log](g12-user-run.9vwiHk.log), actual full timeline tại root `logs/walkthrough.log`, per-demo logs trong root. Original entry chưa append timeline vào user log; D31 entry giữ timeline cả khi FAIL.

## Artifacts để review

- `software.json`, `packaging-check.json`: source/checkout/empty starting artifacts/dependency scope/commands/exits/log hashes/analysis canonical hashes.
- `demos/{basic,baseline,loss,0rtt}`: actual runs/raw/CSV/qlog/progress/PCAP/probes/network/host/cleanup/viewers và conservative `demo-check.json`; local secrets0600.
- `preparation.json`, `logs/preparation-baseline.log`: NEW actual baseline receipt before live (old failed run chưa có).
- `rehearsal.json`, `logs/rehearsal-*.log`, `logs/walkthrough.log`: actual live invocation/timing; `g12-check.json` chỉ có sau final checker thành công.
- [User FAIL audit](g12-user-fail-review.json), [public user-run archive](g12-user-fail-artifacts.tar.gz), [timing regression log](g12-timing-tests.log), [current review](g12-review.json): original failure và patched scope/tests/blocker; public archive excludes keys/keylogs/PCAP/large decoder data, replay cần local original.
- [Patched fresh software receipt](g12-timing-source-software.json), [package check](g12-timing-packaging-check.json), [sudo rerun attempt](g12-timing-system-attempt.log): historical implementation verification trước actual live PASS.

Review ưu tiên separation preparation/live300–420s và checker chronology/hash binding, đủ bốn targets, conservative early/HOL proof/backup labels, UID/PID/capture/idle/cleanup/failure retention, source overlay/offline caches và report/Q&A/ownership. Live loss có thể INCONCLUSIVE với hash-verified labeled pre-recorded G11 backup; actual early phải có decoded REQUEST. Không superiority gate hoặc success-only reruns.

## Historical patched software verification — superseded by full user51c13 PASS

`python3 tests/system/run_g12_software.py --out results/p12-g12-timing-20261002` exit0:14/14steps PASS,UID1000,605 source hashes,base8721f6346bf62cdab9aa653c9105e1ad3ed9516e;12demo+24G12 regressions, actual localhost6/5success+1expectedTLSfailure tại `fresh/results/p11-software-w15sqhkk`,1028 canonical hashes unchanged. [Run log](g12-timing-software-run.log), [receipt](g12-timing-source-software.json), [package](g12-timing-packaging-check.json), [public archive](g12-timing-software-artifacts.tar.gz):130 byte-verified members,SHA7aedfb696634388d011061a5d8fc6f06db8ead9449b371a1dd775a3dafa43738.

Actual system attempt `sudo -n env G12_ROOT="$PWD/results/p12-g12-timing-20261002" bash tests/system/run.sh --gate G12` exit1 **trước runner**: `sudo: interactive authentication is required`. Không automatic approval rejection; không có new actual preparation/live/PCAP. Tại checkpoint lịch sử này patched overall BLOCKED; [attempt](g12-timing-system-attempt.log). Tại checkpoint lịch sử source implementation của fresh tree được đối chiếu current hashes read-only sau reproduction; các cập nhật task/evidence/status là post-run documentation, không đổi tested implementation.

Public [user FAIL archive](g12-user-fail-artifacts.tar.gz):349 byte-verified members,SHA05a238f0cc9983fa5b22edd457970779fb6425c3407c86c615aca4602e7aad92, không rewrite actual root. Full replay cần PCAP/keylogs/decoder local, không có trong public archives.

## Checkpoints lịch sử

- `results/p12-g12-18124ccd073d`:14software/package steps PASS,UID1000,594sourcefiles,base8721f6346bf62cdab9aa653c9105e1ad3ed9516e; localhost6/5success+1expected TLS failure,1028 canonical hashes unchanged. [Receipt](g12-source-software.json), [package](g12-packaging-check.json), [archive](g12-software-artifacts.tar.gz):125byte-verified members,SHA423ea823d65457c63f6d7507fc51994efb1a2bd8f17dab283aabe5d6f440d2ed. [Original sudo attempt](g12-system-attempt.log) exit1 before runner. Preserved [pre-fix review](g12-before-timing-fix-review.json).
- First software `results/p12-g12-5ff24d0a1e30`:13/14PASS,packaging FAIL vì ledger status `PASS actual` thay canonical `PASS`; cell corrected rồi NEW full software14/14PASS. Không rewrite historical source/raw/receipt.
- G11 actual23/23early/HOL/cleanup PASS và [audit/archive](../p11/README.md); self-open check.log exception được disclose, replay process exit không retained nên null, original user gate0 authoritative.

Chỉ P12 được authorize. Sau task/evidence dừng human review; không tự commit/upload/nộp slides hoặc mở phase khác.
