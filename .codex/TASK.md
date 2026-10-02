# TASK — checkpoint hiện hành

Cập nhật: 2026-10-02 (Asia/Saigon).

## Phạm vi và trạng thái

- User authorize tiếp tục hoàn thành P11/G11, gồm xử lý early-secret blocker; chỉ P11, không P12 hoặc commit.
- G10: PASS, actual user-run đã audit tại [P10 evidence](../docs/evidence/p10/README.md).
- G11: current user-run FAIL tại results/p11-g11-1200e3df1cf2,0/23 invoked,cleanup0/host unchanged. D29 PATH/sysctl đã sửa và metadata/lifecycle9 PASS; full rerun pending, lịch sử5/23 giữ nguyên.
- Historical notes giữ nguyên tại [TASK trước khi format](history/TASK-2026-10-02-before-p11-fixes.md); đây là lịch sử, không phải instructions hiện hành.

## Đã thực hiện

- P11 qlog/keylog/progress/viewer và software checks đã PASS; chi tiết ở [P11 evidence](../docs/evidence/p11/README.md).
- Đối chiếu user-run `results/p11-g11-3344e60b5868`: 5/23 trials thành công, actual early Used0RTT=true; shutdown runner exit1, cleanup0, host link/address/route unchanged. Checker chưa chạy; ba handshake PCAP rỗng.
- Lưu lịch sử TASK nguyên văn và chuyển file này thành checkpoint ngắn.
- Sửa shared child wait/signal race, owner environment bằng setpriv reset-env, immediate-mode/flush/EOF capture và reject empty/truncated/count/drop PCAP. Normative refinement ở D27.
- Decode actual early-server PCAP trên derived root riêng: UDP/1RTT đọc được, early REQUEST INCONCLUSIVE vì keylog thiếu CLIENT_EARLY_TRAFFIC_SECRET. Original artifacts/hash/receipts giữ nguyên.
- D28: hash-checked Go1.27.1 build-only TLS overlay thêm hai optional early keylog calls; source/module cache/pins không đổi, không custom crypto. Build receipt lưu generator và original/overlay hashes.
- Actual localhost `results/p11-software-xzfxm1sf`: client/server early secrets matches, qlog PN0/stream0/32 bytes/API qualified;6 trials=5success+1 expected TLS failure. Early6 subcases/full Go/race PASS; chưa PCAP proof.
- G11 precheck actual early PCAP ở cả phía sau3 handshake, trước20 bulk; entry một lệnh `bash scripts/run-g11-review.sh`. Đã yêu cầu user chạy và trả log/exit; agent sudo exit1 trước runner.
- D29 owner PATH gồm trusted sbin/bin ở G11/capture/sink/namespace entry; preflight kiểm owner tools. Exact runtime collector qua production helper/real sysctl đọc7 fields bằng UID1000 và resolve8 tools; [audit](../docs/evidence/p11/g11-path-review.json).14 failed-run files giữ nguyên.

## Đã đọc / inspect

- AGENTS, INDEX, TASK; PLAN P11 và continuity, ACCEPTANCE, NETWORK §7–8/§12, CLI P11, CONTEXT D26.
- Current G11/capture/namespace-entry/common/lifecycle/support/checker, tests audit và qlog shutdown; actual user log/manifest/raw/capture status/host/cleanup.
- Installed setpriv/tcpdump help/manual: reset-env, immediate-mode, packet flush. Read thêm các contracts/code liên quan trước mỗi refinement.
- Pinned Go1.27.1 early handshake/QUIC source/writeKeyLog và quic-go v0.63.0 key events; actual PDML/keylog labels, D28 overlay refinement.
- Resume: PLAN P11/continuity, ACCEPTANCE full, NETWORK§5–8, CLI evidence, PROTOCOL§1–4, METRICS§1–2, DEMO_SPEC§6, CONTEXT D26/D27; inspect build receipt/Makefile, TLS early paths/writeKeyLog, evidence integration/software/checker. Official cmd/go overlay và TLS keylog format.
- Sysctl fix: đọc lại NETWORK§6, CLI P11, PLAN P11, CONTEXT D27/D28; inspect bench-support runtime, G11/capture/sink/namespace reset-env, lifecycle tests và actual root/log/cleanup/host snapshots. Next: explicit trusted PATH gồm sbin ở các owner entries; chạy actual metadata qua production helper trước full rerun.

## Files và kiểm chứng

- Current files: scripts/tls_keylog_overlay.py,build.py,run-g11-review.sh; tests/integration/early_keylog_test.go; system/g11,check_g11,test_audit_p7_p9; Makefile/TASK và docs/evidence. D27 inventory/historical evidence giữ ở [status](../docs/evidence/p11/g11-status.json).

| Lệnh / kiểm | Kết quả | Evidence |
|---|---|---|
| make build; full test/test-race | PASS, exit0 | [build](../docs/evidence/p11/g11-early-build-final.log), [suite](../docs/evidence/p11/g11-early-suite.log), [race](../docs/evidence/p11/g11-early-race.log) |
| early6; provenance4; lifecycle8; detectors6 | PASS, exit0 | [detail](../docs/evidence/p11/g11-early-detail.log), [provenance](../docs/evidence/p11/g11-early-provenance.log), [lifecycle](../docs/evidence/p11/g11-early-lifecycle.log), [detectors](../docs/evidence/p11/g11-early-detectors.log) |
| actual localhost + software checker | PASS software, exit0; full gate remains BLOCKED | [review](../docs/evidence/p11/g11-early-secret-review.json), [checker](../docs/evidence/p11/g11-early-software-check.log) |
| sudo -n full G11 current | BLOCKED, exit1 before runner | [attempt](../docs/evidence/p11/g11-early-system-attempt.log) |
| D29 lifecycle/environment/runtime | PASS, exit0,9 tests; exact collector PASS | [tests](../docs/evidence/p11/g11-path-lifecycle.log), [audit](../docs/evidence/p11/g11-path-review.json) |

Historical D27 analysis/network/audit logs giữ trong P11 README; không rerun G10/network regressions không liên quan. Current build receipt và static audit riêng cho D28, không sửa provenance cũ.

## Vấn đề còn lại

- Actual immediate capture/drain/lifecycle bản sửa chưa chạy vì sudo cần xác thực tương tác.
- Early export blocker đã sửa và verified. Full0RTT REQUEST/HOL proof vẫn cần fresh actual captures; historical missing secret/empty PCAP không thể phục hồi.
- Partial actual run không thay full G11 hoặc packet0RTT/HOL proof; original evidence giữ nguyên.

## Bước tiếp theo

User terminal chạy `bash scripts/run-g11-review.sh` (đã gửi), trả `g11_exit`/`log`. Agent đọc actual root/early-packet-check/g11-check/cleanup, sửa lỗi nếu có, cập nhật acceptance/evidence và dừng P11 review. Không P12/commit; không coi localhost hoặc early precheck riêng là full gate PASS.
