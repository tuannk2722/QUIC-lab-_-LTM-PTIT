#!/usr/bin/env python3
"""Unprivileged lifecycle/provenance regressions; no simulated benchmark data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import build
import tls_keylog_overlay


class AuditTests(unittest.TestCase):
    def test_tls_overlay_preserves_installed_sources_and_rejects_drift(self):
        goroot = REPO / '.tools/go1.27.1'
        if not goroot.exists(): self.skipTest('pinned toolchain not installed')
        originals = {p: (goroot / p).read_bytes() for p in tls_keylog_overlay.PATCHES}
        patched, receipt = tls_keylog_overlay.patched_sources(goroot)
        for path, original in originals.items():
            self.assertEqual((goroot / path).read_bytes(), original)
            self.assertNotEqual(patched[path], original)
            self.assertEqual(patched[path].count(b'writeKeyLog("CLIENT_EARLY_TRAFFIC_SECRET"'), 1)
            self.assertEqual(receipt[path]['original_sha256'], build.digest(goroot / path))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path, original in originals.items():
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_bytes(original)
            first = next(iter(originals))
            (root / first).write_bytes(originals[first] + b'\n// unexpected upstream change\n')
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                tls_keylog_overlay.patched_sources(root)

    def test_build_receipt_rejects_stale_source_and_binaries(self):
        for mutation in ('none', 'source', 'added_source', 'tls_overlay', 'server', 'bench'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name in ('cmd', 'internal', 'scripts', 'bin'):
                    (root / name).mkdir()
                for name in ('go.mod', 'go.sum', 'Makefile', 'scripts/build.py', 'scripts/tls_keylog_overlay.py', 'internal/code.go'):
                    (root / name).write_text('unit fixture')
                for name in build.NAMES:
                    (root / 'bin' / name).write_text('unit ' + name)
                receipt = dict(schema_version=1, inputs=build.inputs(root),
                               binaries={n: build.digest(root / 'bin' / n) for n in build.NAMES})
                if mutation == 'source': (root / 'internal/code.go').write_text('changed')
                elif mutation == 'added_source': (root / 'cmd/new.go').write_text('added')
                elif mutation == 'tls_overlay': (root / 'scripts/tls_keylog_overlay.py').write_text('changed')
                elif mutation in build.NAMES: (root / 'bin' / mutation).write_text('replaced')
                if mutation == 'none': build.verify(receipt, root)
                else:
                    with self.assertRaises(ValueError): build.verify(receipt, root)

    def test_experiment_lock_excludes_second_runner_and_releases(self):
        # Only the ownership preconditions are stubbed for a temporary user
        # directory. Exercise the actual flock function, with no root/network.
        script = '''source scripts/network/common.sh
require_sudo_caller() { :; }
check_state_dir() { :; }
LAB_STATE_DIR=$1
acquire_experiment_lock
printf 'locked\\n'
read -r release
'''
        with tempfile.TemporaryDirectory() as temp:
            first = subprocess.Popen(['bash', '-c', script, 'unit', temp], cwd=REPO,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(first.stdout.readline(), 'locked\n')
                other = subprocess.run(['bash', '-c', script, 'unit', temp], cwd=REPO,
                                       input='release\n', capture_output=True, text=True, timeout=5)
                self.assertEqual(other.returncode, 3, other.stderr)
                self.assertIn('experiment lock', other.stderr)
            finally:
                first.communicate('release\n', timeout=5)
            after = subprocess.run(['bash', '-c', script, 'unit', temp], cwd=REPO,
                                   input='release\n', capture_output=True, text=True, timeout=5)
            self.assertEqual(after.returncode, 0, after.stderr)

    def test_signal_cleanup_with_closed_output_keeps_all_artifacts(self):
        # Reuse actual localhost evidence, never synthesize timings. Exercise
        # the production cleanup body; only no-network operations are stubbed.
        code = (REPO / 'scripts/bench.sh').read_text()
        cleanup = code[code.index('cleanup() {'):code.index('\ntrap cleanup EXIT')]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'experiment'
            shutil.copytree(REPO / 'docs/evidence/p9/actual/success', root)
            for name in ('raw', 'runs.csv', 'streams.csv', 'merge.json', 'summary.csv',
                         'summary.json', 'resource-summary.csv', 'report.md', 'plots'):
                p = root / name
                if p.is_dir(): shutil.rmtree(p)
                elif p.exists(): p.unlink()
            script = '''repo=$1; out=$2
source scripts/bench-lifecycle.sh
run_user() { "$@"; }
stop_process() { forced_stop=false; [[ $1 != unit-trial ]] || return 130; return 0; }
host_compare() { return 0; }
support() { printf '%s %s\\n' "$3" "$4" > "$out/cleanup-unit-status"; }
say() { printf '%s\\n' "$*" 2>/dev/null || true; }
active=false; planned=true; merged=false; analyzed=false
trial_pid=unit-trial; trial_id=; server_pid=; environment_failed=false
''' + cleanup + '''
trap cleanup EXIT
trap 'exit 130' INT
kill -INT "$$"
'''
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
            try:
                p = subprocess.run(['bash', '-c', script, 'unit', str(REPO), str(root)], cwd=REPO,
                                   stdout=write_fd, stderr=subprocess.PIPE, text=True, timeout=40)
            finally:
                os.close(write_fd)
            self.assertEqual(p.returncode, 130, p.stderr)
            self.assertEqual((root / 'cleanup-unit-status').read_text(), '130 0\n')
            for name in ('merge.json', 'summary.csv', 'resource-summary.csv', 'plots/index.json'):
                self.assertTrue((root / name).is_file(), name)
            self.assertEqual(json.loads((root / 'merge.json').read_text())['counts']['n_success'], 6)


if __name__ == '__main__':
    unittest.main()
