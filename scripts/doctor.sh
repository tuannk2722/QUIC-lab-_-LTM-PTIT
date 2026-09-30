#!/usr/bin/env bash
# Read-only P0 inventory. Network primitives need a separate privileged probe.
set -uo pipefail
report=${1:-results/doctor.txt}
mkdir -p -- "$(dirname -- "$report")" || exit 3
inventory() {
status=0
echo "P0 doctor UTC=$(date -u +%FT%TZ)"
echo "repo=$(pwd -P) uid=$(id -u)"
uname -a
cat /etc/os-release
echo 'Resources observed (not a promise of dedicated capacity):'
nproc
free -b
echo 'Host OS/WSL version: see VERSIONS observations; not inferred from the Linux kernel. Revalidate with wsl.exe --version on host.'
if ! grep -qi microsoft /proc/sys/kernel/osrelease; then
    echo 'BLOCKED: current kernel is not the selected WSL2 testbed'; status=3
fi
case "$(pwd -P)" in /mnt/[a-z]/*) echo 'BLOCKED: repo must be in native Linux filesystem'; status=3 ;; esac
if [[ $(id -u) == 0 ]]; then echo 'BLOCKED: run builds and doctor as normal user'; status=3; fi
for tool in go git make openssl ip tc tcpdump ethtool python3; do
    if ! command -v "$tool"; then echo "BLOCKED: missing $tool"; status=3; continue; fi
    case "$tool" in
        go) go version || status=3; expected_go=$(awk '$1 == "go" {print $2}' go.mod); [[ $(go version) == "go version go$expected_go "* ]] || status=3 ;;
        openssl) openssl version || status=3 ;;
        ip|tc) "$tool" -V || status=3 ;;
        *) "$tool" --version || status=3 ;;
    esac
done
echo 'Kernel modules (loaded or built in does not prove packet path):'
for module in sch_netem ifb act_mirred veth; do
    if [[ -d /sys/module/$module ]]; then echo "$module present"; else echo "UNVERIFIED: $module not visible in sysfs"; fi
done
echo 'Namespaces currently visible:'
ip netns list || { echo 'BLOCKED: cannot inspect namespaces'; status=3; }
echo 'Python plotting libraries (P9; absence does not fail P0):'
python3 - <<'PY'
import importlib.metadata
for name in ('matplotlib', 'numpy', 'pandas'):
    try:
        print(name, importlib.metadata.version(name))
    except importlib.metadata.PackageNotFoundError:
        print(name, 'not installed; deferred to P9')
PY
echo 'Capability probe: NOT_RUN by read-only doctor; use sudo bash scripts/preflight-network.sh separately.'
echo 'Neither inventory nor primitive probe passes G07/G08; no topology/impairment benchmark was run.'
echo "doctor_exit=$status report=$report"
exit "$status"
}
inventory 2>&1 | tee "$report"
codes=("${PIPESTATUS[@]}")
if [[ ${codes[1]} != 0 ]]; then exit 3; fi
exit "${codes[0]}"
