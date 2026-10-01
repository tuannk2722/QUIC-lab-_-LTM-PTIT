#!/usr/bin/env python3
"""Actual G09 gate: cohort, provenance, network, derived output and cleanup."""
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'analysis'))
sys.path.insert(0, str(REPO / 'scripts'))
from cohort import digest, load
from summarize import COLUMNS, GROUP, summarize_rows
from validate import require


def read(path):
    return json.loads(path.read_text())


def check(root, interrupted=False):
    runs, streams, plan, result = load(root, main=not interrupted)
    merge = read(root / 'merge.json')['counts']
    cleanup = read(root / 'cleanup.json')
    require(cleanup['cleanup_exit'] == 0 and all(cleanup['host_unchanged'].values()), 'cleanup/host state failed')
    require(not cleanup['environment_failed'], 'environment failed')
    require(merge['n_success']+merge['n_failed'] == merge['n_attempted'] == len(runs), 'failure denominator differs')
    require(merge['n_missing_shards'] == sum(not (root / 'shards' / r['run_id'] / 'raw' / (r['run_id']+'.json')).exists() for r in runs),
            'missing count differs')
    if interrupted:
        require(cleanup['original_exit'] == 130 and merge['n_failed'] >= 1 and merge['n_invoked'] < merge['n_planned'],
                'interrupt/missing representation failed')
        require(any(r['error_code'] in ('interrupted', 'cancelled', 'not_started', 'missing_shard') for r in runs), 'no interrupt failure row')
    else:
        require(cleanup['original_exit'] in (0, 1) and merge['n_invoked'] == 256 and merge['n_missing_shards'] == 0,
                'full main invocations/shards missing')
        require(all(r['error_code'] not in ('environment_error', 'not_started', 'missing_shard', 'interrupted', 'result_write_error', 'runner_error') for r in runs),
                'infrastructure/runner incomplete dataset')
        for r in runs:
            rid = r['run_id']
            require(read(root / 'network' / f'{rid}.check.json')['status'] == 'PASS', 'network validity failed')
            for side in ('before', 'after'):
                snap = read(root / 'network' / f'{rid}.{side}.json')
                require(snap['verified'] and snap['netem_seed'] == r['netem_seed'] and snap['scenario'] == r['scenario'], 'snapshot differs')
            require((root / 'logs' / f'{rid}.invocation.json').exists(), 'invocation journal missing')
            if r['success']:
                info = read(root / 'shards' / rid / 'connection.json')
                require(info['tls_version'] == 'TLS 1.3' and info['alpn'] == 'quicbench/1' and not info['did_resume'], 'actual TLS differs')
                require(info['send_buffer_bytes'] > 0 and info['receive_buffer_bytes'] > 0, 'actual client socket buffer missing')
                if r['transport'] == 'quic':
                    require(info['used_0rtt'] is False and info['quic_version'] == 'v1', 'cold QUIC state differs')
        probes = list((root / 'probes').glob('*.log.json'))
        require(len(probes) == 4 and all(read(p)['status'] == 'PASS' for p in probes), 'actual RTT probes missing')
        require(read(root / 'runtime.json')['uid'] > 0, 'application metadata from root')
    expected = summarize_rows(runs)
    with (root / 'summary.csv').open(newline='') as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames == COLUMNS, 'summary header differs')
        actual = list(reader)
    encoded = [{k: '' if r[k] is None else str(r[k]) for k in COLUMNS} for r in expected]
    require(actual == encoded, 'summary not derived from CSV')
    require(all(r['n_success']+r['n_failed'] == r['n_attempted'] for r in expected), 'summary denominator differs')
    plots = read(root / 'plots/index.json')
    require(len(plots['files']) == 8 and all((root / p).stat().st_size > 1000 for p in plots['files']), 'exported plots missing/empty')
    artifacts = {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file() and p.name not in ('g09-check.json', 'gate-summary.json')}
    status = dict(gate='G09', status='PASS', scope='interrupt' if interrupted else 'main', counts=result,
                  merge_counts=merge, artifact_sha256=artifacts,
                  limitations='Performance observations only; HOL causal evidence and early modes await P10/P11.')
    (root / 'g09-check.json').write_text(json.dumps(status, indent=2)+'\n')
    return dict(status='PASS', scope=status['scope'], counts=result, artifacts_hashed=len(artifacts))


if __name__ == '__main__':
    try:
        root = Path(sys.argv[1])
        print(json.dumps(check(root, '--interrupted' in sys.argv[2:]), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'G09 check FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
