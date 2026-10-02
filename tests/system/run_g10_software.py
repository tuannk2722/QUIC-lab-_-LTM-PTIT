#!/usr/bin/env python3
"""Complete counts on real localhost sockets; never IFB performance evidence."""
import json
import os
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
from check_g10 import check, check_functional


def main():
    require_uid = os.getuid()
    if require_uid == 0:
        raise ValueError('application/analysis must be unprivileged')
    os.chdir(REPO)
    root = Path(tempfile.mkdtemp(prefix='p10-software-', dir=REPO / 'results'))
    commands, server = [], None
    def run(args, name, expected=0, env=None):
        log = root / (name + '.log')
        with log.open('x') as f:
            p = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT, timeout=180, check=False, env=env)
        commands.append(dict(argv=args, exit_code=p.returncode, log=str(log.relative_to(root))))
        if p.returncode != expected:
            raise ValueError(f'{name}: exit {p.returncode} expected {expected}; {log.read_text()}')
    try:
        functional = root / 'functional'
        functional.mkdir()
        env = dict(os.environ, GOTOOLCHAIN='local', GOPATH=str(REPO / '.tools/gopath'), GOCACHE=str(REPO / '.tools/gocache'),
                   GOMAXPROCS='2', GOFLAGS='-p=2', QUICLAB_G10_RECORDS=str(functional))
        run([str(REPO / '.tools/go1.27.1/bin/go'), 'test', '-mod=readonly', '-count=1', '-v', '-run', '^TestSession', './tests/integration'],
            'functional-tests', env=env)
        check_functional(functional)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        endpoint, ready = f'127.0.0.1:{port}', root / 'ready'
        with (root / 'server.log').open('x') as log:
            server = subprocess.Popen(['bin/server', '--transport=both', '--profile=handshake', '--allow-0rtt=true',
                                       f'--listen={endpoint}', f'--ready-file={ready}'], stdout=log, stderr=subprocess.STDOUT)
        for _ in range(100):
            if ready.exists():
                break
            if server.poll() is not None:
                raise ValueError('server exited before readiness')
            time.sleep(.05)
        if not ready.exists():
            raise ValueError('server readiness timeout')
        for mode in ('cold', 'resumed', 'early'):
            run(['bin/client', '--transport=quic', '--profile=handshake', f'--mode={mode}', f'--addr={endpoint}',
                 '--server-name=localhost', '--format=json', f'--out={root / ("client-"+mode)}'], 'client-'+mode)
        common = ['bin/bench', '--suite=handshake', f'--addr={endpoint}', '--server-name=localhost']
        success = root / 'success'
        run(common + [f'--out={success}'], 'suite96')
        summarize(success)
        plot(success)
        status = check(success, software=True)
        failure = root / 'tls-failure'
        run(common + ['--runs=1', '--warmups=0', '--server-name=wrong.invalid', f'--out={failure}'], 'tls-failure', expected=1)
        _, _, _, failures = load(failure)
        if failures['attempted'] != 3 or failures['failed'] != 3:
            raise ValueError('three-mode failures were filtered')
        summarize(failure)
        plot(failure)
        server.terminate()
        if server.wait(timeout=10) != 0 or ready.exists():
            raise ValueError('server shutdown/readiness cleanup failed')
        server = None
        status = dict(status='PASS', scope='actual localhost correctness; not G10 IFB/main performance', result_root=str(root),
                      uid=require_uid, commands=commands, suite=status, failure=failures,
                      artifact_sha256={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file()})
        (root / 'software-review.json').write_text(json.dumps(status, indent=2)+'\n')
        print(json.dumps({k:v for k,v in status.items() if k!='artifact_sha256'},indent=2))
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    main()
