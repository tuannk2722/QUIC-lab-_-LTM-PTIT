#!/usr/bin/env python3
"""Unprivileged P9 metadata/checks. Shell owns namespace/qdisc/process lifecycle."""
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'analysis'))
sys.path.insert(0, str(REPO / 'tests/system'))
sys.path.insert(0, str(REPO / 'scripts'))
from cohort import digest
from check_g08 import netem, probe
from build import load_verified, launch_verified


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def read(path):
    return json.loads(Path(path).read_text())


def put(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def pinned():
    wanted = dict(line.strip().split('==') for line in (REPO / 'analysis/requirements.txt').read_text().splitlines()
                  if line.strip() and not line.startswith('#'))
    installed = {d.metadata['Name'].lower(): d.version for d in importlib.metadata.distributions(path=[str(REPO / '.tools/analysis')])}
    for name, version in wanted.items():
        if installed.get(name.lower()) != version:
            raise ValueError(f'analysis dependency {name}=={version} absent/different; run make analysis-deps as user')
    return installed


def check_network(root, rid, publish=True):
    root = Path(root)
    before, after = read(root / 'network' / f'{rid}.before.json'), read(root / 'network' / f'{rid}.after.json')
    plan = read(root / 'schedule.json')
    entry = next(e for e in plan['entries'] if e['run_id'] == rid)
    scenario = next(s for s in plan['scenarios']['scenarios'] if s['name'] == entry['scenario'])
    details = {}
    status, error = 'PASS', ''
    try:
        expected = dict(schema_version=1, verified=True, network_profile='ingress-ifb', scenario=entry['scenario'],
                        netem_seed=entry['netem_seed'], config_sha256=plan['scenarios_sha256'],
                        queue_limit_packets=plan['scenarios']['queue_limit_packets'], mtu=plan['scenarios']['mtu'],
                        **{k: scenario[k] for k in ('delay_each_way_ms', 'loss_downstream_pct', 'loss_upstream_pct', 'rate_mbps')})
        for key, value in expected.items():
            if before[key] != value or after[key] != value:
                raise ValueError(f'network differs from schedule: {key}')
        for key in ('client_namespace_id', 'server_namespace_id', 'seed_status'):
            if before[key] != after[key]:
                raise ValueError(f'network identity/status changed: {key}')
        for ns in ('qclient', 'qserver'):
            b, a = netem(before, ns), netem(after, ns)
            delta = {k: a[k] - b[k] for k in ('bytes', 'packets', 'drops', 'overlimits')}
            if any(n < 0 for n in delta.values()):
                raise ValueError('counters reset during trial')
            pattern = r'Sent (\d+) bytes (\d+) pkt'
            bs = re.findall(pattern, before['observation'][ns]['filters_text'])
            ats = re.findall(pattern, after['observation'][ns]['filters_text'])
            if len(bs) != 1 or len(ats) != 1:
                raise ValueError('redirect counter unavailable')
            delta['redirect_packets'] = int(ats[0][1]) - int(bs[0][1])
            details[ns] = delta
        path = root / 'shards' / rid / 'raw' / f'{rid}.json'
        if path.exists():
            run = read(path)['run']
            if run['success']:
                for ns in ('qclient', 'qserver'):
                    if details[ns]['packets'] <= 0 or details[ns]['redirect_packets'] <= 0:
                        raise ValueError(f'{ns} shaping/redirect counters did not increase')
                if details['qclient']['bytes'] < run['bytes_received']:
                    raise ValueError('downstream direction/bytes sanity failed')
                # A 1 KiB exchange is dominated by handshake/control. The
                # sustained-bulk ratio/rate criteria do not apply to it.
                if plan.get('suite', 'bulk') != 'handshake' and details['qclient']['bytes'] <= 5*details['qserver']['bytes']:
                    raise ValueError('downstream direction/bytes sanity failed')
                if scenario['loss_downstream_pct'] > 0 and details['qclient']['drops'] <= 0:
                    raise ValueError('successful loss trial showed no downstream drops')
                if plan.get('suite', 'bulk') != 'handshake' and (run['goodput_mbps'] is None or not 0 < run['goodput_mbps'] <= scenario['rate_mbps'] * 1.1):
                    raise ValueError('payload goodput rate sanity failed')
    except (ValueError, KeyError, StopIteration, TypeError) as exc:
        status, error = 'FAIL', str(exc)
    if publish:
        put(root / 'network' / f'{rid}.check.json', dict(schema_version=1, run_id=rid, status=status, error=error, details=details))
    if status != 'PASS':
        raise ValueError(error)
    return details


def idle(before, after):
    b, a = read(before), read(after)
    for ns in ('qclient', 'qserver'):
        for snap in (b, a):
            q = netem(snap, ns)
            if q.get('backlog', 0) != 0 or q.get('qlen', 0) != 0:
                raise ValueError('shaping queue is not drained')
        if netem(b, ns)['packets'] != netem(a, ns)['packets']:
            raise ValueError('lab traffic remains between client invocations')


def runtime(root):
    values = {'timestamp_utc': now(), 'uid': os.getuid(), 'gid': os.getgid(), 'python': sys.version, 'analysis_packages': pinned()}
    for key in ['net.core.rmem_default', 'net.core.wmem_default', 'net.core.rmem_max', 'net.core.wmem_max',
                'net.ipv4.tcp_rmem', 'net.ipv4.tcp_wmem', 'net.ipv4.tcp_congestion_control']:
        p = subprocess.run(['sysctl', '-n', key], text=True, capture_output=True, check=False)
        values[key] = p.stdout.strip() if p.returncode == 0 else 'unknown: ' + p.stderr.strip()
    put(Path(root) / 'runtime.json', values)


def invocation(root, rid, exit_code=None):
    path = Path(root) / 'logs' / f'{rid}.invocation.json'
    if exit_code is None:
        if path.exists():
            raise ValueError('invocation already logged')
        obj = dict(schema_version=1, run_id=rid, started_utc=now(), ended_utc='', exit_code=None)
    else:
        obj = read(path)
        obj.update(ended_utc=now(), exit_code=int(exit_code))
    put(path, obj)


def cleanup(root, original, cleanup_exit, environment_failed):
    root = Path(root)
    comparison = {}
    for kind in ['link', 'address', 'route']:
        comparison[kind] = (root / 'host' / f'{kind}.before.json').read_bytes() == (root / 'host' / f'{kind}.final.json').read_bytes()
    put(root / 'cleanup.json', dict(original_exit=int(original), cleanup_exit=int(cleanup_exit),
                                  environment_failed=environment_failed == 'true', host_unchanged=comparison, timestamp_utc=now()))


def main():
    op, *args = sys.argv[1:]
    if os.getuid() == 0:
        raise ValueError('metadata/check/analysis must run unprivileged')
    if op == 'preflight':
        load_verified(REPO / 'bin/build.json')
        pinned()
        if read(REPO / 'docs/evidence/p8/g08-status.json')['status'] != 'PASS':
            raise ValueError('actual G08 must be PASS before main cohort')
    elif op == 'runtime':
        runtime(*args)
    elif op == 'invocation':
        invocation(*args)
    elif op == 'network':
        check_network(*args)
    elif op == 'idle':
        idle(*args)
    elif op == 'probe':
        probe(*args)
    elif op == 'cleanup':
        cleanup(*args)
    elif op == 'list':
        for e in read(Path(args[0]) / 'schedule.json')['entries']:
            seed = str(e['netem_seed']) if e['netem_seed'] is not None else 'none'
            print(f"{e['run_id']}\t{e['scenario']}\t{seed}")
    elif op == 'launch-verified':
        log, root, name, *argv = args
        launch_verified(log, root, name, argv)
    elif op == 'launch-log':
        log, program, *argv = args
        with open(log, 'x') as target:
            os.dup2(target.fileno(), 1)
            os.dup2(target.fileno(), 2)
        os.execv(program, [program, *argv])
    else:
        raise ValueError('unknown operation')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(f'bench support FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
