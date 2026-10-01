#!/usr/bin/env python3
"""Actual unprivileged localhost runner checks; never main performance evidence."""
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'analysis'))
from cohort import digest, load
from summarize import summarize
from plot import plot


def main():
    os.chdir(REPO)
    root = Path(tempfile.mkdtemp(prefix='p9-software-', dir=REPO / 'results'))
    commands = []
    server = None
    def run(args, expected=0, name=None):
        log = root / ((name or f'command-{len(commands)}') + '.log')
        with log.open('w') as f:
            p = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT, timeout=40, check=False)
        commands.append(dict(argv=args, exit_code=p.returncode, log=str(log)))
        if p.returncode != expected:
            raise AssertionError(f'{args}: exit {p.returncode} expected {expected}; {log.read_text()}')
    def stop():
        nonlocal server
        if server:
            server.terminate()
            if server.wait(timeout=10) != 0:
                raise AssertionError('server stop failed')
            server = None
    try:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        endpoint = f'127.0.0.1:{port}'
        ready = root / 'ready'
        with (root / 'server.log').open('w') as log:
            server = subprocess.Popen(['bin/server', '--transport=both', '--profile=bulk', f'--listen={endpoint}', f'--ready-file={ready}'],
                                      stdout=log, stderr=subprocess.STDOUT)
        for _ in range(100):
            if ready.exists():
                break
            if server.poll() is not None:
                raise AssertionError('server exited before readiness')
            time.sleep(.05)
        assert ready.exists()
        common = ['bin/bench', f'--addr={endpoint}', '--server-name=localhost', '--profile=bulk']
        run(common + ['--plan', f'--out={root / "default-plan"}'], name='default-plan')
        entries = json.loads((root / 'default-plan/schedule.json').read_text())['entries']
        assert len(entries) == 256 and sum(e['phase'] == 'measured' for e in entries) == 240
        assert not (root / 'default-plan/runs.csv').exists()  # Planning is not a trial/gate PASS.
        success = root / 'success'
        run(common + ['--runs=2', '--warmups=1', '--scenario=baseline', f'--out={success}'], name='success')
        _, _, _, counts = load(success)
        assert counts['attempted'] == counts['success'] == 6 and counts['failed'] == 0
        assert counts['measured_trials'] == 4 and counts['warmup_trials_excluded'] == 2
        run([sys.executable, 'scripts/bench-support.py', 'launch-verified', str(root / 'verified-exec-output.log'),
             str(success), 'bench', '--version'], name='verified-exec')
        failure = root / 'tls-failure'
        run(common + ['--server-name=wrong.invalid', '--runs=1', '--warmups=0', '--scenario=baseline', f'--out={failure}'], expected=1, name='tls-failure')
        _, _, _, counts = load(failure)
        assert counts['attempted'] == counts['failed'] == 2 and counts['success'] == 0
        partial = root / 'interrupted'
        run(common + ['--plan', '--network-profile=loopback-test', '--runs=2', '--warmups=0', '--scenario=baseline', f'--out={partial}'], name='partial-plan')
        plan = json.loads((partial / 'schedule.json').read_text())
        entry = plan['entries'][0]
        run([sys.executable, 'scripts/bench-support.py', 'invocation', str(partial), entry['run_id']], name='partial-start-success')
        run(['bin/bench', f'--schedule-entry={partial / "entries" / (entry["run_id"] + ".json")}'], name='partial-success')
        run([sys.executable, 'scripts/bench-support.py', 'invocation', str(partial), entry['run_id'], '0'], name='partial-end-success')
        stop()
        # Actual stalled endpoints keep both TLS/QUIC setup in flight until a
        # real SIGKILL before output. This tests missing-shard reconstruction;
        # its zero elapsed sentinel is never used as a latency observation.
        tcp = socket.socket()
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp.bind(('127.0.0.1', port)); tcp.listen()
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind(('127.0.0.1', port))
        try:
            duplicate = root / 'duplicate'
            run(common + ['--plan', '--network-profile=loopback-test', '--runs=1', '--warmups=0',
                          '--scenario=baseline', f'--out={duplicate}'], name='duplicate-plan')
            dplan = json.loads((duplicate / 'schedule.json').read_text())
            de = next(e for e in dplan['entries'] if e['transport'] == 'tcp')
            dcmd = ['bin/bench', f'--schedule-entry={duplicate / "entries" / (de["run_id"] + ".json")}']
            with (root / 'duplicate-first.log').open('w') as log:
                process = subprocess.Popen(dcmd, stdout=log, stderr=subprocess.STDOUT)
                try:
                    tcp.settimeout(5)
                    conn, _ = tcp.accept()  # First trial has actually dialed.
                    with conn:
                        run(dcmd, expected=1, name='duplicate-refused')
                        tcp.settimeout(.2)
                        try:
                            extra, _ = tcp.accept()
                        except socket.timeout:
                            pass
                        else:
                            extra.close()
                            raise AssertionError('duplicate entry opened a second connection')
                finally:
                    process.kill()
                    process.wait(timeout=5)
            entry = plan['entries'][1]
            run([sys.executable, 'scripts/bench-support.py', 'invocation', str(partial), entry['run_id']], name='partial-start-killed')
            with (root / 'killed-process.log').open('w') as log:
                process = subprocess.Popen(['bin/bench', f'--schedule-entry={partial / "entries" / (entry["run_id"] + ".json")}'], stdout=log, stderr=subprocess.STDOUT)
                time.sleep(.1)
                assert process.poll() is None
                process.kill()
                assert process.wait(timeout=5) == -signal.SIGKILL
            run([sys.executable, 'scripts/bench-support.py', 'invocation', str(partial), entry['run_id'], '137'], name='partial-end-killed')
        finally:
            tcp.close(); udp.close()
        run(['bin/bench', f'--merge={partial}'], expected=1, name='partial-merge')
        runs, streams, _, counts = load(partial)
        assert counts['attempted'] == 4 and counts['success'] == 1 and counts['failed'] == 3 and len(streams) == 24
        assert sum(r['error_code'] == 'not_started' for r in runs) == 2
        assert sum(r['error_code'] == 'interrupted' for r in runs) == 1
        for case in (success, failure, partial):
            summarize(case)
            plot(case)
            run(['bin/bench', f'--merge={case}'], expected=1, name=case.name+'-overwrite-refused')
            for raw in (case / 'shards').glob('*/connection.json'):
                info = json.loads(raw.read_text())
                assert info['tls_version'] == 'TLS 1.3' and info['alpn'] == 'quicbench/1' and not info['did_resume']
        review = {'scope': 'P9 software and actual localhost correctness; no applied impairment or main cohort',
                  'status': 'PASS', 'result_root': str(root), 'commands': commands,
                  'cases': {name: load(root / name)[3] for name in ('success', 'tls-failure', 'interrupted')},
                  'default_plan': {'entries': 256, 'measured_planned': 240, 'warmup_planned': 16, 'executed': False},
                  'artifact_sha256': {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file()}}
        (root / 'software-review.json').write_text(json.dumps(review, indent=2)+'\n')
        print(json.dumps({k: review[k] for k in ('scope', 'status', 'result_root', 'cases', 'default_plan')}, indent=2))
    finally:
        stop()


if __name__ == '__main__':
    main()
