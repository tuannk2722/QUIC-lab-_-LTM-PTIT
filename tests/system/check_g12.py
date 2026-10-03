#!/usr/bin/env python3
"""P12 packaging audit and actual fresh-tree demo/rehearsal acceptance."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_prior_gates(fresh):
    ledger = (fresh / 'docs/ACCEPTANCE_RESULTS.md').read_text()
    acceptance = {}
    for i in range(12):
        gate = f'G{i:02}'
        rows = [line for line in ledger.splitlines() if re.match(r'\| ' + gate + r'(?:[- /|])', line)]
        # The overall network gates must PASS; a historical software subcase
        # cannot replace actual network/capture acceptance.
        if i >= 7:
            overall = [line for line in rows if 'overall' in line.split('|')[1]]
            require(len(overall) == 1 and overall[0].split('|')[2].strip() == 'PASS', gate + ' overall not PASS')
            rows = overall
        else:
            rows = [line for line in rows if '| PASS' in line]
        paths = []
        for row in rows:
            for link in re.findall(r'\]\(([^)]+)\)', row):
                if link.startswith('evidence/') and (fresh / 'docs' / link).exists():
                    paths.append(link)
        require(rows and paths, gate + ' has no passing evidence in ledger')
        acceptance[gate] = sorted(set(paths))
    # Bind the latest actual G11 closure to its reviewed public bundle and
    # actual 23-entry/proof/cleanup requirements, not just a prose PASS label.
    review = json.loads((fresh / 'docs/evidence/p11/g11-rerun-review.json').read_text())
    result = review['checker_original']
    require(review['status'] == 'PASS' and review['user_gate_exit'] == 0 and result['status'] == 'PASS', 'G11 actual gate failed')
    require(result['counts'] == {'n_planned': 23, 'n_invoked': 23, 'n_success': 23, 'n_failed': 0}, 'G11 incomplete denominator')
    require(result['early_proof'] == 'PASS' and result['hol'] == 'PASS' and result['full_demo_complete'], 'G11 packet/HOL proof incomplete')
    require(review['cleanup']['original_exit'] == 0 and review['cleanup']['cleanup_exit'] == 0 and all(review['host_byte_identical'].values()), 'G11 cleanup failed')
    archive = review['archive']
    require(archive['byte_verified'] and digest(fresh / archive['path']) == archive['sha256'], 'G11 public archive differs from audited evidence')
    return acceptance


def check_source(software, fresh):
    source = Path(software['source_root'])
    for name, value in software['source_hashes'].items():
        require(digest(fresh / name) == value, 'exported source changed: ' + name)
    implementation = ('cmd/', 'internal/', 'scripts/', 'analysis/', 'tests/', 'configs/', 'schemas/')
    selected = {name: value for name, value in software['source_hashes'].items()
                if name.startswith(implementation) or name in ('Makefile', 'go.mod', 'go.sum')}
    current = {str(p.relative_to(source)): digest(p) for directory in implementation
               for p in (source / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts
               and p.suffix in ('.go', '.py', '.sh', '.json', '.txt')}
    current.update({name: digest(source / name) for name in ('Makefile', 'go.mod', 'go.sum')})
    selected = {name: value for name, value in selected.items() if Path(name).suffix in ('.go', '.py', '.sh', '.json', '.txt') or name in ('Makefile', 'go.mod', 'go.sum')}
    require(current == selected, 'current implementation changed since fresh source export; rerun G12')


def check_make_steps(root, record, phase, targets):
    elapsed = record['elapsed_seconds']
    require(record['status'] == 'PASS' and record['uid'] > 0 and record['offline'] is True
            and math.isfinite(elapsed) and elapsed > 0, phase + ' did not PASS offline as ordinary user')
    require([s['name'] for s in record['steps']] == list(targets), 'missing/reordered ' + phase + ' Make target')
    previous = 0
    for step, target in zip(record['steps'], targets.values()):
        require(step['exit'] == 0 and step['argv'][:2] == ['make', target], 'failed/wrong ' + phase + ' Make target')
        if step['name'] != 'cleanup':
            require('DEMO_OUT=' + str(root / 'demos' / step['name']) in step['argv'], 'wrong demo output directory')
        start, end = step['start_seconds'], step['end_seconds']
        require(math.isfinite(start) and math.isfinite(end) and previous <= start <= end <= elapsed,
                phase + ' command times outside recorded clock')
        previous = end
        require(step['log'] == 'logs/' + phase + '-' + step['name'] + '.log', 'wrong ' + phase + ' log path')
        require(digest(root / step['log']) == step['sha256'], 'rehearsal log changed')


def check_rehearsal(root, rehearsal):
    require(rehearsal['status'] == 'PASS' and 300 <= rehearsal['elapsed_seconds'] <= 420,
            'offline terminal walkthrough must take 5–7 minutes')
    require(rehearsal['schema_version'] == 2 and
            rehearsal['presentation_policy'] == 'timed terminal walkthrough; human oral delivery not certified',
            'rehearsal must disclose delivery scope and separate preparation')
    bound = rehearsal['preparation']
    require(bound['path'] == 'preparation.json' and digest(root / bound['path']) == bound['sha256'],
            'preparation receipt changed')
    preparation = json.loads((root / bound['path']).read_text())
    require(preparation['scope'] == 'baseline Make acceptance before live A→C→B clock' and
            preparation['uid'] == rehearsal['uid'], 'baseline preparation scope/owner differs')
    from datetime import datetime
    require(datetime.fromisoformat(preparation['started_utc']) <= datetime.fromisoformat(preparation['finished_utc'])
            <= datetime.fromisoformat(rehearsal['started_utc']) <= datetime.fromisoformat(rehearsal['finished_utc']),
            'baseline preparation must finish before live clock')
    check_make_steps(root, preparation, 'preparation', {'baseline': 'demo-baseline'})
    check_make_steps(root, rehearsal, 'rehearsal',
                     {'basic': 'demo-quic-basic', 'loss': 'demo-loss', '0rtt': 'demo-0rtt', 'cleanup': 'cleanup'})
    return preparation


def check(root, software_only=False):
    software = json.loads((root / 'software.json').read_text())
    fresh = Path(software['fresh_root'])
    require(software['uid'] > 0, 'software/build application UID must be nonroot')
    require(software['empty_build_cache'], 'fresh build cache required')
    require(software['starting_artifacts'] == {'bin': [], 'certs': ['.gitkeep'], 'results': ['.gitkeep']},
            'fresh source contains inherited app/cert/results')
    check_source(software, fresh)
    checkout = software['checkout']
    require(Path(subprocess.check_output(['git', '-C', str(fresh), 'rev-parse', '--show-toplevel'], text=True).strip()) == fresh,
            'fresh checkout inherited parent VCS')
    require(subprocess.check_output(['git', '-C', str(fresh), 'rev-parse', 'HEAD'], text=True).strip() == checkout['base_commit']
            and checkout['candidate_overlay'] and not checkout['new_commit'], 'fresh candidate checkout receipt invalid')
    required = {'modules', 'build', 'certs', 'doctor', 'go-tests', 'analysis-tests', 'network-tests',
                'demo-tests', 'g12-tests', 'localhost', 'localhost-check', 'analyze', 'public-targets'}
    steps = {s['name']: s for s in software['steps']}
    require(required <= steps.keys(), 'missing reproduction steps: ' + str(required - steps.keys()))
    for step in steps.values():
        require(step['exit'] == 0 and digest(root / step['log']) == step['sha256'],
                'failed or changed reproduction log: ' + step['name'])
    cohort = Path(software['analysis_root'])
    for name, value in software['analysis_raw_hashes'].items():
        require(digest(cohort / name) == value, 'analysis modified source data: ' + name)
    source_manifest = json.loads((fresh / 'docs/references/SOURCE_MANIFEST.json').read_text())
    for item in source_manifest['files']:
        p = fresh / 'docs/references/originals' / item['file']
        require(p.stat().st_size == item['bytes'] and digest(p) == item['sha256'], 'historical original changed')
    acceptance = check_prior_gates(fresh)
    for name in ('README.md', 'docs/DEMO_SCRIPT.md', 'docs/REPORT.md', 'docs/AI_USAGE.md',
                 'docs/THEORY_AND_DEFENSE.md', 'docs/evidence/p12/README.md', 'scripts/demo.sh'):
        require((fresh / name).is_file(), 'missing package document/entry: ' + name)
    report = dict(schema_version=1, scope='fresh source software and packaging' if software_only else 'full G12',
                  status='PASS', mandatory_prior_gate_evidence=acceptance,
                  source_files=len(software['source_hashes']), originals_unchanged=True,
                  current_source_export=True, fresh_local_checkout=True, committed_candidate=False,
                  limitation='prepared offline dependency caches reused; no inherited application binaries/certs/results',
                  software_root=str(root), full_gate=not software_only)
    if not software_only:
        require(software['status'] == 'PASS', 'software reproduction failed')
        rehearsal = json.loads((root / 'rehearsal.json').read_text())
        require(rehearsal['uid'] == software['uid'], 'rehearsal owner differs from fresh software')
        preparation = check_rehearsal(root, rehearsal)
        demos = {}
        import importlib.util
        spec = importlib.util.spec_from_file_location('demo_support', fresh / 'scripts/demo-support.py')
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        for kind in ('basic', 'baseline', 'loss', '0rtt'):
            summary_path = root / 'demos' / kind / 'demo-check.json'
            summary = json.loads(summary_path.read_text())
            require(summary['status'] == 'PASS', 'demo failed: ' + kind)
            verifier.verify(summary_path.parent)
            cleanup = json.loads((summary_path.parent / 'cleanup.json').read_text())
            require(cleanup['original_exit'] == 0 and cleanup['cleanup_exit'] == 0, 'demo cleanup failed: ' + kind)
            demos[kind] = dict(check=str(summary_path.relative_to(root)), sha256=digest(summary_path),
                               completed_check_log_sha256=digest(summary_path.parent / 'logs/check.log'), summary=summary)
        report.update(demos=demos, preparation=preparation, rehearsal=rehearsal,
                      human_review='pending: code ownership, oral presentation and slide submission')
    target = root / ('packaging-check.json' if software_only else 'g12-check.json')
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--software', action='store_true')
    args = parser.parse_args()
    try:
        result = check(args.root.resolve(), args.software)
        print(json.dumps(dict(status=result['status'], scope=result['scope'], source_files=result['source_files'])))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('G12 check FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
