# P7/G07 evidence — through 2026-10-01 UTC

P7 shell topology, privilege entry, Make targets and the G07 system runner are implemented. **G07 currently FAILS**: the first real system run reached host-state verification, then stopped because two host IFBs appeared. Setup has been changed to request `numifbs=0` before namespace IFB creation; recovery and the full rerun have not happened. The G00 capability probe and localhost Go tests do not satisfy G07.

## First real G07 run, supplied by the user

- UTC start `2026-10-01T00:23:06Z`; command `sudo bash tests/system/run.sh 2>&1 | tee docs/evidence/p7/g07-system.log` under Ubuntu WSL2. The log has `G07 FAIL: host link state changed at pass1-active`; a numeric shell exit status was not captured separately. Result path: `results/p7-g07-JqV32x/host-state/` (real host link/address/route snapshots). No TCP/QUIC result directories were produced.
- Observed PASS before the stop: foreign qclient collision refused without deletion; injected qclient setup failure rolled back; first owned qclient/qserver setup and repeated setup worked; UID/GID dropped to `1000:1000`; 3/3 ICMP replies in each direction. First teardown removed the owned namespaces. `ip netns list` outside the sandbox is now empty.
- Host link before had only `lo` and `eth0`. At pass1-active, `ifb0` and `ifb1` appeared on the host. They remain DOWN/noop with no addresses; current host link/address/route JSON matches the failed active snapshots byte for byte. Updated `g07-host-recovery-check.log` is a read-only recovery precheck that exits 0 and finds no host tc filters referencing the IFBs. **Recovery has not been executed**, so do not claim host state was restored.
- The mutating recovery path refused an unprivileged invocation with exit 3; see `g07-host-recovery-nonroot.log`. No IFB was removed by that check.
- Kernel source [drivers/net/ifb.c](https://github.com/torvalds/linux/blob/master/drivers/net/ifb.c) initializes `numifbs=2` by default and registers legacy devices in `init_net`; this explains the observed host interfaces. Setup now calls `modprobe ifb numifbs=0` before creating namespace IFBs. This change has not been tested by the real system gate. The module is already loaded in the current WSL boot, so a rerun after recovery verifies the topology and host state in this boot; the first load after a fresh boot remains untested.

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

The sandbox itself denied `ip netns list` with EPERM and prevented sudo through `no new privileges`; read-only `ip netns list` outside sandbox succeeded. The user subsequently ran the system gate interactively and exposed the IFB host-side effect. No G07 TCP/QUIC traffic or performance result has been produced.

## Recover host IFBs and rerun in an interactive Ubuntu WSL2 terminal

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

The rerun must exit 0 and print the final `PASS: G07 ...` line. The runner prints a fresh `results_dir`, verifies both transport records with `analysis/validate.py`, and leaves four actual cold result directories plus `host-state/` JSON snapshots there. Review the full log, numeric exit status, result paths and host comparisons before changing `G07-system` from FAIL. If the runner fails, inspect its cleanup output and use `sudo bash scripts/network/teardown.sh` only for namespaces still matching this lab's ownership marker; it refuses unrelated names or active PIDs. Never delete a colliding namespace just by name.

P7 client records still carry the P6 `loopback-test` network label even when used on the namespace path. They are correctness evidence only. IFB ingress mirred/netem, RTT/rate/loss counters and benchmark results belong to G08/G09.
