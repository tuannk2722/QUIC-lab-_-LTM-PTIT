#!/usr/bin/env python3
"""Fresh current-source reproduction, with disclosed prepared offline dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def put(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def offline_environment(fresh):
    env = dict(os.environ)
    for name in ('QLOGDIR', 'GOROOT', 'GOMODCACHE', 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
        env.pop(name, None)
    env.update(GOPROXY='off', GOSUMDB='off', GOTOOLCHAIN='local', GOENV='off',
               GOPATH=str(fresh / '.tools/gopath'), GOCACHE=str(fresh / '.tools/gocache'),
               PATH=str(fresh / '.tools/go1.27.1/bin') + ':' + os.environ['PATH'],
               GIT_CEILING_DIRECTORIES=str(fresh.parent))
    return env


def export_source(destination):
    # Genuine fresh LOCAL checkout, followed by the exact review candidate.
    # No commit/push of the user's working tree is necessary to test its patch.
    subprocess.run(['git', 'clone', '--no-local', '--no-checkout', '--quiet', str(REPO), str(destination)], check=True)
    subprocess.run(['git', '-C', str(destination), 'checkout', '--detach', '--quiet', 'HEAD'], check=True)
    for item in destination.iterdir():
        if item.name != '.git':
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink()
    files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=REPO).decode().split('\0')
    inventory = {}
    for name in sorted(set(files) - {''}):
        source = REPO / name
        if not source.is_file():
            continue  # Deleted working-tree files are intentionally absent.
        if source.is_symlink() or name.startswith(('.git/', '.tools/', 'bin/', 'certs/', 'results/')) and name not in ('certs/.gitkeep', 'results/.gitkeep'):
            raise ValueError('unexpected export path: ' + name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        inventory[name] = digest(target)
    for name in ('certs', 'results', '.tools'):
        (destination / name).mkdir(exist_ok=True)
    # Prepared dependencies only: no prior app image, certificate, result or
    # build cache. Offline downloads are a README prerequisite, not a live step.
    for name in ('go1.27.1', 'gopath', 'analysis', 'tshark'):
        source = REPO / '.tools' / name
        if not source.is_dir():
            raise ValueError('prepare offline dependency first: ' + str(source))
        (destination / '.tools' / name).symlink_to(source, target_is_directory=True)
    return inventory


def reproduce(root):
    if os.getuid() == 0:
        raise ValueError('fresh build/tests must run as an ordinary user')
    root = root.resolve()
    root.mkdir(parents=True)  # Refuse overwrite of any previous gate.
    logs = root / 'logs'
    logs.mkdir()
    fresh = root / 'fresh'
    fresh.mkdir()
    receipt = dict(schema_version=1, status='IN_PROGRESS', uid=os.getuid(), source_root=str(REPO),
                   fresh_root=str(fresh), export_policy='fresh local checkout plus exact current tracked/nonignored candidate overlay; no commit created',
                   prepared_offline_dependencies=['Go1.27.1', 'module cache', 'pinned analysis packages', 'pinned decoder'],
                   empty_build_cache=True, steps=[])
    put(root / 'software.json', receipt)
    env = offline_environment(fresh)

    def run(name, command):
        started = time.monotonic()
        log = logs / (name + '.log')
        with log.open('x') as target:
            rc = subprocess.run(command, cwd=fresh, env=env, stdout=target, stderr=subprocess.STDOUT).returncode
        receipt['steps'].append(dict(name=name, argv=command, exit=rc, elapsed_seconds=time.monotonic()-started,
                                     log=str(log.relative_to(root)), sha256=digest(log)))
        put(root / 'software.json', receipt)
        print(f'G12 software: {name} exit={rc} log={log}', flush=True)
        if rc:
            raise ValueError(f'{name} failed; see {log}')
        return log

    try:
        receipt['source_hashes'] = export_source(fresh)
        receipt['checkout'] = dict(base_commit=subprocess.check_output(['git', '-C', str(fresh), 'rev-parse', 'HEAD'], text=True).strip(),
                                   local_origin=str(REPO), candidate_overlay=True, new_commit=False)
        receipt['starting_artifacts'] = {name: sorted(p.name for p in (fresh / name).iterdir()) if (fresh / name).exists() else []
                                         for name in ('bin', 'certs', 'results')}
        put(root / 'software.json', receipt)
        run('modules', [str(fresh / '.tools/go1.27.1/bin/go'), 'mod', 'verify'])
        run('build', ['make', 'build', 'BUILD=source-export'])
        run('certs', ['make', 'certs'])
        run('doctor', ['make', 'doctor', 'REPORT=results/g12-doctor.txt'])
        run('go-tests', ['make', 'test'])
        run('analysis-tests', ['make', 'test-analysis'])
        run('network-tests', ['make', 'test-network'])
        run('demo-tests', ['make', 'test-demo'])
        run('g12-tests', ['python3', 'tests/system/test_g12.py', '-v'])
        log = run('localhost', ['python3', 'tests/system/run_g11_software.py'])
        match = next(line for line in log.read_text().splitlines() if line.startswith('software_root='))
        software = Path(match.split('=', 1)[1])
        run('localhost-check', ['python3', 'tests/system/check_g11.py', str(software), '--software'])
        receipt['localhost_root'] = str(software)
        # Regenerate from an archived real performance dataset; raw is extracted
        # into this NEW tree, never modified at its original path.
        import tarfile
        archive = fresh / 'docs/evidence/p9/g09-user-run-artifacts.tar.gz'
        cohort = fresh / 'results/g12-analysis'
        cohort.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(cohort, filter='data')
        candidates = [p.parent for p in cohort.rglob('schedule.json') if p.parent.name == 'main']
        if len(candidates) != 1:
            raise ValueError('archived main cohort missing or ambiguous')
        cohort = candidates[0]
        raw_before = {str(p.relative_to(cohort)): digest(p) for p in cohort.rglob('*')
                      if p.is_file() and (p.parts[-2] == 'raw' or p.name in ('runs.csv', 'streams.csv', 'schedule.json', 'manifest.json', 'build.json'))}
        run('analyze', ['make', 'analyze', 'RESULTS=' + str(cohort)])
        if any(digest(cohort / name) != value for name, value in raw_before.items()):
            raise ValueError('analysis modified canonical source data')
        receipt.update(analysis_root=str(cohort), analysis_raw_hashes=raw_before)
        run('public-targets', ['make', '-n', 'benchmark', 'benchmark-handshake', 'cleanup'])
        run('packaging-check', ['python3', 'tests/system/check_g12.py', str(root), '--software'])
        receipt.update(status='PASS', actual_network_rehearsal='NOT_RUN')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        receipt.update(status='FAIL', error=str(error))
        raise
    finally:
        put(root / 'software.json', receipt)
    print('gate_root=' + str(root), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    arguments = parser.parse_args()
    try:
        reproduce(arguments.out)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('G12 software FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
