#!/usr/bin/env python3
"""Build receipt binds app sources to exact executables; ordinary user only."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from tls_keylog_overlay import prepare

REPO = Path(__file__).resolve().parents[1]
NAMES = ('server', 'client', 'bench')


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def inputs(repo):
    paths = [repo / name for name in ('go.mod', 'go.sum', 'Makefile', 'scripts/build.py', 'scripts/tls_keylog_overlay.py')]
    for directory in ('cmd', 'internal'):
        paths.extend(p for p in (repo / directory).rglob('*.go') if not p.name.endswith('_test.go'))
    return {str(p.relative_to(repo)): digest(p) for p in sorted(paths)}


def verify(receipt, repo=REPO):
    if receipt.get('schema_version') != 1 or receipt.get('inputs') != inputs(repo):
        raise ValueError('build source changed or receipt invalid; run make build')
    if set(receipt.get('binaries', {})) != set(NAMES):
        raise ValueError('build receipt has incomplete binaries')
    for name in NAMES:
        if digest(repo / 'bin' / name) != receipt['binaries'][name]:
            raise ValueError(f'build binary changed: {name}; run make build')
    return receipt


def load_verified(path, repo=REPO):
    return verify(json.loads(Path(path).read_text()), repo)


def launch_verified(log, root, name, argv):
    if name not in NAMES:
        raise ValueError('unknown application binary')
    receipt = load_verified(Path(root) / 'build.json')
    # Execute the descriptor just hashed, not a path that a concurrent build
    # could replace between verification and exec. Applications never run root.
    with (REPO / 'bin' / name).open('rb') as executable:
        if hashlib.file_digest(executable, 'sha256').hexdigest() != receipt['binaries'][name]:
            raise ValueError('binary changed before exec')
        with open(log, 'x') as target:
            os.dup2(target.fileno(), 1)
            os.dup2(target.fileno(), 2)
        os.execve(executable.fileno(), [str(REPO / 'bin' / name), *argv], dict(os.environ))


def build(go, revision):
    if os.getuid() == 0:
        raise ValueError('build must run as an ordinary user')
    bindir = REPO / 'bin'
    bindir.mkdir(exist_ok=True)
    with (bindir / '.build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = inputs(REPO)
        flags = ['-mod=readonly', '-trimpath', '-ldflags', f'-X quic-performance-lab/internal/cli.Build={revision}']
        with tempfile.TemporaryDirectory(prefix='.build-', dir=bindir) as temp:
            stage = Path(temp)
            overlay, tls_receipt = prepare(go, stage / 'tls-overlay')
            for name in NAMES:
                subprocess.run([go, 'build', '-overlay='+str(overlay), *flags, '-o', str(stage / name), './cmd/' + name], cwd=REPO, check=True)
            if inputs(REPO) != before:
                raise ValueError('sources changed during build; no binaries published')
            receipt = dict(schema_version=1, inputs=before, binaries={n: digest(stage / n) for n in NAMES},
                           go_version=subprocess.check_output([go, 'version'], text=True).strip(),
                           build_flags=['-overlay=<temporary hash-checked TLS overlay>', *flags], tls_keylog_overlay=tls_receipt)
            (stage / 'build.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
            # Receipt is last: any partial publication is rejected by verify.
            for name in (*NAMES, 'build.json'):
                os.replace(stage / name, bindir / name)


if __name__ == '__main__':
    try:
        if sys.argv[1] == 'verify':
            load_verified(REPO / 'bin/build.json')
        else:
            build(*sys.argv[1:])
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'build provenance: {exc}', file=sys.stderr)
        sys.exit(1)
