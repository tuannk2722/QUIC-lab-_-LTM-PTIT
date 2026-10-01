# P7/G07 evidence — through 2026-10-01 UTC

P7/G07 hiện **PASS**. Người dùng chạy recovery exit0 và toàn bộ rerun UTC 2026-10-01T01:09:39Z, g07_exit=0. `g07-system-rerun.log` có hai vòng topology, TCP+QUIC, UID drop, SIGINT/no-orphan và host-state comparisons. `results/p7-g07-vNiIgt/` giữ bốn real cold trial dirs/host snapshots. Agent đối chiếu artifacts khi mở P8; `g07-rerun-review.json` lưu log hash và kiểm CSV/count/hash/host equality. Không tự nhận agent chạy sudo hoặc user đã review toàn bộ code.

## First real G07 run — lịch sử đã được recovery/rerun thay thế

User run UTC 00:23:06Z tại `g07-system.log`, snapshots `results/p7-g07-JqV32x/host-state/`, FAIL tại pass1-active do IFB module mặc định numifbs=2 sinh hai host interfaces. Collision/rollback/topology/UID/ping vòng1 đạt, transfer chưa chạy trong lần đó. Setup sửa modprobe ifb numifbs=0; guarded recovery thực exit0 ở `g07-host-recovery.log`, rerun sau đó PASS. `g07-host-recovery-check.log` và nonroot log giữ như lịch sử. Host IFBs từ lần lỗi không còn theo recovery log, không cần recovery lại. Nguồn driver: [ifb.c](https://github.com/torvalds/linux/blob/master/drivers/net/ifb.c). Module đã loaded trong boot hiện tại; first load sau fresh boot vẫn chưa kiểm.

## Earlier agent checks (2026-09-30)

| Command | Actual result | Artifact |
|---|---|---|
| `make build` | exit 0, three binaries built by UID 1000 | `g07-build.log` |
| `make test` outside sandbox, UID 1000 | exit 0; Go suite reports cached packages; no Go code changed in P7 | `g07-go-suite.log` |
| `bash -n scripts/network/*.sh scripts/run-in-netns.sh tests/system/run.sh` | exit 0 | terminal result; no output on success |
| `make -n setup-network server clean-network` | exit 0; recipes inspected, not executed | `g07-make-dry-run.log` |
| `bash tests/system/run.sh` without sudo | exit 3; refuses to run system gate without root | `g07-nonroot.log` |
| `bash scripts/run-in-netns.sh qclient -- /usr/bin/id` without sudo | exit 3, `Namespace entry requires sudo.` | terminal result |
| `sudo -n bash tests/system/run.sh` outside sandbox | exit 1 before runner starts: `sudo: interactive authentication is required` | `g07-system-attempt.log` |

The sandbox itself denied `ip netns list` with EPERM and prevented sudo through `no new privileges`; read-only `ip netns list` outside sandbox succeeded. The user subsequently ran the system gate interactively and exposed the IFB host-side effect. Lần rerun sau đó có G07 TCP/QUIC correctness traffic; không có performance/impairment result.

## Lệnh recovery/rerun đã dùng (historical reproduction)

From the repo root, first check the exact failed-run snapshots and remove only the two verified, unused host IFBs. The recovery script refuses if the host changed since the snapshot, if the devices are active/configured, if host tc filters are present, or if qclient/qserver still exists. It rechecks before each deletion and can resume after a partial deletion; avoid concurrent host network changes during recovery:

```bash
bash scripts/network/restore-host-ifb.sh --check-only results/p7-g07-JqV32x/host-state
set -o pipefail
sudo bash scripts/network/restore-host-ifb.sh results/p7-g07-JqV32x/host-state 2>&1 | tee docs/evidence/p7/g07-host-recovery.log
recovery_status=${PIPESTATUS[0]}; printf 'recovery_exit=%s\n' "$recovery_status" | tee -a docs/evidence/p7/g07-host-recovery.log
```

Only after recovery exits 0, with no qclient/qserver namespace or lab marker:

```bash
make build
test -r certs/server.crt && test -r certs/server.key || make certs
mkdir -p results
set -o pipefail
sudo bash tests/system/run.sh 2>&1 | tee docs/evidence/p7/g07-system-rerun.log
g07_status=${PIPESTATUS[0]}; printf 'g07_exit=%s\n' "$g07_status" | tee -a docs/evidence/p7/g07-system-rerun.log
```

The rerun must exit 0 and print the final `PASS: G07 ...` line. The runner prints a fresh `results_dir`, verifies both transport records with `analysis/validate.py`, and leaves four actual cold result directories plus `host-state/` JSON snapshots there. Rerun đã đạt các bước này và current G07-system PASS; giữ lệnh để reproduction, không chạy recovery lại khi không còn IFB lỗi. If the runner fails, inspect its cleanup output and use `sudo bash scripts/network/teardown.sh` only for namespaces still matching this lab's ownership marker; it refuses unrelated names or active PIDs. Never delete a colliding namespace just by name.

P7 client records still carry the P6 `loopback-test` network label even when used on the namespace path. They are correctness evidence only. IFB ingress mirred/netem, RTT/rate/loss counters and benchmark results belong to G08/G09.
