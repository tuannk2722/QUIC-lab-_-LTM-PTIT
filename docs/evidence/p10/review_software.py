#!/usr/bin/env python3
"""Recheck actual localhost artifacts on a copy and byte-verify their archive."""
import csv
import hashlib
import json
import math
import shutil
import statistics
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'tests/system'))
from check_g10 import check, check_functional


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main(root):
    root = Path(root).resolve()
    out = Path(__file__).resolve().parent
    original = json.loads((root / 'software-review.json').read_text())
    require(original['status'] == 'PASS' and original['uid'] > 0, 'software review absent/root apps')
    for name, expected in original['artifact_sha256'].items():
        require(sha(root / name) == expected, 'as-run artifact changed: ' + name)
    with tempfile.TemporaryDirectory(prefix='g10-review-') as tmp:
        copy = Path(tmp) / root.name
        shutil.copytree(root, copy)
        functional = check_functional(copy / 'functional')
        suite = check(copy / 'success', software=True)
    # Independent arithmetic directly from CSV, excluding unachieved early
    # targets using actual state plus successful REQUEST completion timing.
    success = root / 'success'
    with (success / 'runs.csv').open(newline='') as f:
        runs = {r['run_id']: r for r in csv.DictReader(f)}
    with (success / 'streams.csv').open(newline='') as f:
        streams = {r['run_id']: r for r in csv.DictReader(f)}
    eligible, unachieved = {}, []
    for rid, r in runs.items():
        yes = r['success'] == 'true' and r['fallback_count'] == '0'
        if r['mode'] == 'early':
            yes = yes and r['tls_resumed'] == r['used_0rtt'] == r['attempted_0rtt'] == 'true' and r['early_rejected'] == 'false'
            yes = yes and bool(streams[rid]['request_end_ms']) and bool(r['handshake_ms']) and float(streams[rid]['request_end_ms']) < float(r['handshake_ms'])
        elif r['mode'] == 'resumed':
            yes = yes and r['tls_resumed'] == 'true' and r['used_0rtt'] == r['attempted_0rtt'] == 'false'
        else:
            yes = yes and r['tls_resumed'] == r['used_0rtt'] == r['attempted_0rtt'] == 'false'
        eligible[rid] = yes
        if r['phase'] == 'measured' and r['success'] == 'true' and not yes:
            unachieved.append(rid)
    with (success / 'summary.csv').open(newline='') as f:
        summaries = list(csv.DictReader(f))
    for s in summaries:
        group = [r for r in runs.values() if r['phase'] == 'measured' and r['mode'] == s['mode']]
        values = sorted(float(r[s['metric']]) for r in group if eligible[r['run_id']] and r[s['metric']])
        require(int(s['n_attempted']) == len(group) == 30 and int(s['n_values']) == len(values), 'summary denominator differs')
        expected = {'mean': statistics.mean(values), 'median': statistics.median(values),
                    'p95': values[math.ceil(.95 * len(values))-1], 'sample_stddev': statistics.stdev(values)}
        for key, value in expected.items():
            require(math.isclose(float(s[key]), value, rel_tol=1e-10, abs_tol=1e-10), 'summary arithmetic differs: ' + key)
    with (success / 'resource-summary.csv').open(newline='') as f:
        resource_summaries = list(csv.DictReader(f))
    for s in resource_summaries:
        group = [r for r in runs.values() if r['phase'] == 'measured' and r['mode'] == s['mode']]
        require(s['resource_id'] == '1', 'handshake resource distribution differs')
        values = sorted(float(streams[r['run_id']][s['metric']]) for r in group if eligible[r['run_id']])
        require(int(s['n_attempted']) == 30 and int(s['n_values']) == len(values), 'resource denominator differs')
        expected = {'mean': statistics.mean(values), 'median': statistics.median(values),
                    'p95': values[math.ceil(.95*len(values))-1], 'sample_stddev': statistics.stdev(values)}
        for key, value in expected.items():
            require(math.isclose(float(s[key]), value, rel_tol=1e-10, abs_tol=1e-10), 'resource arithmetic differs: ' + key)
    files = {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}
    require(not any('key' in Path(p).name.lower() for p in files), 'unexpected key artifact')
    archive = out / 'localhost-artifacts.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for name in sorted(files):
            tar.add(root / name, arcname=root.name + '/' + name, recursive=False)
    with tarfile.open(archive, 'r:gz') as tar:
        require(len(tar.getmembers()) == len(files), 'archive count differs')
        for name, expected in files.items():
            f = tar.extractfile(root.name + '/' + name)
            require(f is not None and hashlib.file_digest(f, 'sha256').hexdigest() == expected, 'archive bytes differ: ' + name)
    source = json.loads((success / 'source-hashes.json').read_text())
    changed = [p for p, h in source.items() if not (REPO / p).exists() or sha(REPO / p) != h]
    current = {str(p.relative_to(REPO)) for directory in ('internal', 'cmd', 'scripts', 'analysis', 'configs', 'schemas', 'tests')
               for p in (REPO / directory).rglob('*') if p.is_file() and p.suffix in ('.go', '.py', '.sh', '.json', '.txt')}
    added = sorted(current - set(source))
    result = dict(status='PASS', scope='actual localhost correctness, not IFB performance or packet0RTT proof',
                  source_root=str(root), functional=functional, suite=suite, summary_groups_recomputed=len(summaries),
                  resource_summary_groups_recomputed=len(resource_summaries),
                  unachieved_successful_measured=unachieved, as_run_inventory_verified=True,
                  artifact_sha256=files, archive=dict(path=archive.name, sha256=sha(archive), files=len(files), byte_verified=True),
                  current_checker_sha256=sha(REPO / 'tests/system/check_g10.py'),
                  source_changed_since_run=changed,
                  source_added_since_run=added,
                  provenance_note='As-run source hashes/receipt retained. Checker hardening and test fixture refinements are reviewed separately; no as-run evidence rewritten.')
    (out / 'localhost-review.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'artifact_sha256'}, indent=2))


if __name__ == '__main__':
    main(sys.argv[1])
