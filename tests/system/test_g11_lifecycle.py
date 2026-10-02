#!/usr/bin/env python3
"""P11 regressions; fixtures exercise lifecycle, never measured network proof."""
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import struct
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('capture_support', REPO / 'scripts/evidence-support.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


class LifecycleTests(unittest.TestCase):
    def shell(self, code, *args, env=None):
        return subprocess.run(['bash', '-euo', 'pipefail', '-c',
                               'source scripts/process-lifecycle.sh\n' + code,
                               'regression', *map(str, args)], cwd=REPO,
                              env=env, capture_output=True, text=True, timeout=10)

    def test_exit_between_check_and_kill_uses_wait_status(self):
        # Force a stale liveness observation after a real child has exited.
        for exit_code in (0, 7):
            with self.subTest(exit_code=exit_code):
                p = self.shell('''bash -c 'exit "$1"' child "$1" & child_pid=$!
sleep .1
managed_process_running() { return 0; }
stop_process "$child_pid" false 0
''', exit_code)
                self.assertEqual(p.returncode, 0 if exit_code == 0 else 1, p.stderr)
                self.assertNotIn('No such process', p.stderr)

    def test_graceful_exit_and_signalled_child_are_distinguished(self):
        p = self.shell('''sleep 30 & child_pid=$!
if stop_process "$child_pid" false; then exit 9; fi
sleep 30 & child_pid=$!
stop_process "$child_pid" true
''')
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_deadline_kills_only_owned_child_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self.shell('''python3 -c 'import signal,sys,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path(sys.argv[1]).touch(); time.sleep(30)' "$1" & child_pid=$!
for ((i=0;i<100;i++)); do [[ -e $1 ]] && break; sleep .01; done
[[ -e $1 ]]
if stop_process "$child_pid" true 2; then exit 9; fi
if kill -0 "$child_pid" 2>/dev/null; then exit 8; fi
''', Path(temp) / 'ready')
            self.assertEqual(p.returncode, 0, p.stderr)

    def test_production_run_user_resets_root_environment_and_keeps_seed(self):
        # Ordinary test UID cannot init supplementary groups. Only substitute
        # that privileged operation; execute real setpriv --reset-env.
        caller = pwd.getpwuid(os.getuid())
        dirty_env = dict(os.environ, HOME='/root', USER='root', LOGNAME='root',
                         XDG_CONFIG_HOME='/root/.config', WIRESHARK_CONFIG_DIR='/root/.config/wireshark',
                         NETEM_SEED='none')
        for path in ('tests/system/g11.sh', 'scripts/capture.sh'):
            with self.subTest(path=path):
                definition = next(line for line in (REPO / path).read_text().splitlines()
                                  if line.startswith('run_user()'))
                code = '''SUDO_UID=$(id -u); SUDO_GID=$(id -g)
setpriv() {
 local -a arguments=()
 for argument in "$@"; do
  if [[ $argument == --init-groups ]]; then arguments+=(--keep-groups); else arguments+=("$argument"); fi
 done
 command setpriv "${arguments[@]}"
}
''' + definition + '''
run_user python3 -c 'import os,json,shutil; result={k:os.environ.get(k) for k in ["HOME","USER","LOGNAME","XDG_CONFIG_HOME","WIRESHARK_CONFIG_DIR","NETEM_SEED","PATH"]}; result["sysctl"]=shutil.which("sysctl"); print(json.dumps(result))'
'''
                p = self.shell(code, env=dirty_env)
                self.assertEqual(p.returncode, 0, p.stderr)
                result = json.loads(p.stdout)
                self.assertEqual(result['HOME'], caller.pw_dir)
                self.assertEqual(result['USER'], caller.pw_name)
                self.assertEqual(result['LOGNAME'], caller.pw_name)
                self.assertIsNone(result['XDG_CONFIG_HOME'])
                self.assertIsNone(result['WIRESHARK_CONFIG_DIR'])
                self.assertEqual(result['NETEM_SEED'], 'none' if path.endswith('g11.sh') else None)
                self.assertEqual(result['PATH'], '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
                self.assertIsNotNone(result['sysctl'])

    def test_runtime_metadata_through_production_owner_entry(self):
        # No namespace simulation or sysctl stub: run the exact failed command
        # as the ordinary UID with the actual owner environment function.
        definition = next(line for line in (REPO / 'tests/system/g11.sh').read_text().splitlines()
                          if line.startswith('run_user()'))
        with tempfile.TemporaryDirectory() as temp:
            code = '''SUDO_UID=$(id -u); SUDO_GID=$(id -g)
setpriv() {
 local -a arguments=()
 for argument in "$@"; do
  if [[ $argument == --init-groups ]]; then arguments+=(--keep-groups); else arguments+=("$argument"); fi
 done
 command setpriv "${arguments[@]}"
}
''' + definition + '\nrun_user python3 scripts/bench-support.py runtime "$1"\n'
            p = self.shell(code, temp, env=dict(os.environ, HOME='/root', XDG_CONFIG_HOME='/root/.config'))
            self.assertEqual(p.returncode, 0, p.stderr)
            metadata = json.loads((Path(temp) / 'runtime.json').read_text())
            self.assertEqual(metadata['uid'], os.getuid())
            self.assertEqual(metadata['net.ipv4.tcp_congestion_control'],
                             Path('/proc/sys/net/ipv4/tcp_congestion_control').read_text().strip())

    def test_namespace_entry_uses_owner_environment(self):
        # Execute the production namespace-entry tail with only namespace
        # entry/group clearing substituted. Real reset-env must remove XDG.
        entry = (REPO / 'scripts/run-in-netns.sh').read_text().split('exec ip netns exec', 1)[1]
        caller = pwd.getpwuid(os.getuid())
        with tempfile.TemporaryDirectory() as temp:
            fake_ip = Path(temp) / 'ip'
            fake_ip.write_text('''#!/usr/bin/env bash
set -euo pipefail
[[ $1 == netns && $2 == exec && $3 == qserver && $4 == setpriv ]]
shift 4
arguments=()
for argument in "$@"; do
 if [[ $argument == --clear-groups ]]; then arguments+=(--keep-groups); else arguments+=("$argument"); fi
done
exec /usr/bin/setpriv "${arguments[@]}"
''')
            fake_ip.chmod(0o700)
            code = 'SUDO_UID=$(id -u); SUDO_GID=$(id -g); ns=qserver\nset -- python3 -c ' + \
                   "'import json,os,shutil;print(json.dumps([os.environ[\"HOME\"],os.environ.get(\"XDG_CONFIG_HOME\"),shutil.which(\"sysctl\")]))'\n" + \
                   'exec ip netns exec' + entry
            p = self.shell(code, env=dict(os.environ, HOME='/root', XDG_CONFIG_HOME='/root/.config',
                                          PATH=temp + ':' + os.environ['PATH']))
            self.assertEqual(p.returncode, 0, p.stderr)
            result = json.loads(p.stdout)
            self.assertEqual(result[:2], [caller.pw_dir, None])
            self.assertIsNotNone(result[2])

    def test_capture_status_rejects_empty_truncated_and_unflushed_dump(self):
        # Binary fixture only: it is not published as packet evidence.
        header = struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 262144, 1)
        packet = struct.pack('<IIII', 1, 0, 4, 4) + b'test'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for data, logged_count, accepted in [(header, 0, False),
                                               (header + packet[:-1], 1, False),
                                               (header + packet, 2, False),
                                               (header + packet, 1, True)]:
                with self.subTest(size=len(data), logged_count=logged_count):
                    (root / 'capture.pcap').write_bytes(data)
                    (root / 'tcpdump.log').write_text(f'{logged_count} packet{ "s" if logged_count != 1 else ""} captured\n0 packets dropped by kernel\n')
                    status = support.capture_status(root, 'qclient', 143, 0)
                    self.assertEqual(status['capture_complete'], accepted)
                    self.assertEqual(status['cleanup_exit'], 0 if accepted else 1)
            (root / 'tcpdump.log').write_text('1 packet captured\n1 packet dropped by kernel\n')
            self.assertFalse(support.capture_status(root, 'qclient', 143, 0)['capture_complete'])

    def test_real_failed_run_empty_capture_is_not_promoted(self):
        root = REPO / 'results/p11-g11-3344e60b5868/captures'
        if not root.exists():
            self.skipTest('historical local evidence unavailable in fresh checkout')
        for ns in ('qclient', 'qserver'):
            result = support.capture_status(root / 'handshake_cold' / ns, ns, 143, 0)
            self.assertEqual(result['capture_packets'], 0)
            self.assertFalse(result['capture_complete'])
        result = support.capture_status(root / 'loss_0_quic/qclient', 'qclient', 143, 0)
        self.assertTrue(result['capture_complete'], result['capture_error'])

    def test_archived_checker_rejects_actual_empty_capture_on_copy(self):
        source = REPO / 'results/p11-g11-3344e60b5868'
        if not source.exists():
            self.skipTest('historical local evidence unavailable in fresh checkout')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'actual-copy'
            shutil.copytree(source, root)
            p = subprocess.run(['python3', 'tests/system/check_g11.py', str(root)],
                               cwd=REPO, capture_output=True, text=True, timeout=30)
            self.assertEqual(p.returncode, 1, p.stderr)
            failure = json.loads((root / 'g11-failure.json').read_text())
            self.assertIn('capture incomplete:', failure['error'])
            self.assertEqual(support.pcap_packets(source / 'captures/handshake_cold/qclient/capture.pcap'), 0)


if __name__ == '__main__':
    unittest.main()
