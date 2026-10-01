#!/usr/bin/env python3
"""CSV-derived statistics. Every planned failure remains in the denominator."""
import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from cohort import load

GROUP = ['scenario', 'transport', 'mode', 'network_profile', 'trace_mode', 'resource_count', 'resource_size_bytes', 'chunk_bytes']
METRICS = ['total_ms', 'ttfa_ms', 'goodput_mbps', 'e2e_goodput_mbps', 'handshake_ms']
COLUMNS = GROUP + ['metric', 'n_attempted', 'n_success', 'n_failed', 'failure_rate', 'n_values', 'mean', 'median', 'p95', 'sample_stddev', 'n_timeout', 'failure_codes']


def stats(values):
    values = sorted(values)
    if not values:
        return {'n_values': 0, 'mean': None, 'median': None, 'p95': None, 'sample_stddev': None}
    return {'n_values': len(values), 'mean': statistics.mean(values), 'median': statistics.median(values),
            'p95': values[math.ceil(.95 * len(values)) - 1],
            'sample_stddev': statistics.stdev(values) if len(values) > 1 else None}


def summarize_rows(rows, fields=GROUP, metrics=METRICS):
    groups = defaultdict(list)
    for row in rows:
        if row['phase'] == 'measured':
            groups[tuple(row[k] for k in fields)].append(row)
    result = []
    for group, trials in sorted(groups.items()):
        successes = [r for r in trials if r['success']]
        failures = Counter(r['error_code'] for r in trials if not r['success'])
        for metric in metrics:
            result.append(dict(zip(fields, group), metric=metric, n_attempted=len(trials), n_success=len(successes),
                               n_failed=len(trials)-len(successes), failure_rate=(len(trials)-len(successes))/len(trials),
                               n_timeout=failures['timeout'], failure_codes=json.dumps(failures, sort_keys=True),
                               **stats([r[metric] for r in successes if r[metric] is not None])))
    return result


def write_csv(path, rows, columns):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def summarize(directory, main=False):
    runs, streams, plan, counts = load(directory, main)
    result = summarize_rows(runs)
    write_csv(directory / 'summary.csv', result, COLUMNS)
    by_run = {r['run_id']: r for r in runs}
    resources = []
    for s in streams:
        r = by_run[s['run_id']]
        # Each resource distribution has one sample per successful RUN; do not
        # pool six correlated resources into six independent trial samples.
        resources.append(dict(s, **{k: r[k] for k in GROUP}, phase=r['phase'],
                              success=r['success'] and s['success'], error_code=r['error_code']))
    fields = GROUP + ['resource_id']
    resource_stats = summarize_rows(resources, fields, ['complete_ms', 'first_byte_ms'])
    write_csv(directory / 'resource-summary.csv', resource_stats, fields + COLUMNS[len(GROUP):])
    notes = {'counts': counts, 'scheduled_denominator': True, 'latency_policy': 'successful measured runs only; all failures reported',
             'warmups_excluded': counts['warmup_trials_excluded'], 'p95': 'nearest-rank ceil(.95*n)-1',
             'stddev': 'sample n-1; null for n<2', 'resource_policy': 'separate distribution per resource_id; correlated siblings are not independent trials',
             'main_checked': main, 'experiment_id': plan['experiment_id']}
    (directory / 'summary.json').write_text(json.dumps(notes, indent=2) + '\n')
    body = ['# P9 CSV-derived results', '', f"Experiment: `{plan['experiment_id']}`; execution: `{plan['execution']}`.", '',
            f"All scheduled rows: {counts['attempted']}; success {counts['success']}; failed {counts['failed']}; "
            f"measured {counts['measured_trials']}; excluded warmups {counts['warmup_trials_excluded']}.", '',
            'Latency/goodput summarize successful measured trials. Failures remain in every denominator. '
            'p95 is nearest-rank; sample stddev is null below two observations. No outliers removed.', '',
            '| Scenario | Transport | Metric | Attempted | Success | Failed | Median | p95 |',
            '|---|---|---|---:|---:|---:|---:|---:|']
    for r in result:
        if r['metric'] not in ('total_ms', 'ttfa_ms', 'goodput_mbps'):
            continue
        def number(k): return '—' if r[k] is None else f"{r[k]:.3f}"
        body.append(f"| {r['scenario']} | {r['transport']} | {r['metric']} | {r['n_attempted']} | {r['n_success']} | {r['n_failed']} | {number('median')} | {number('p95')} |")
    body += ['', 'Artifacts: runs.csv, streams.csv, raw/, schedule.json, manifest.json, merge.json, summary.csv, resource-summary.csv and plots/.', '',
             'Limitations: shared WSL2 host/kernel/CPU, different kernel/userspace transport and scheduling, differing packetization/congestion control; '
             'paired seed does not imply identical lost application bytes. Configured loss affects downstream control/ACK traffic too; '
             'qdisc drops can include overflow. Small cohorts/p95 describe this testbed and workload. Performance plots do not establish HOL causation. '
             'P10 resumption/early and P11 qlog/PCAP/progress evidence remain pending.', '']
    (directory / 'report.md').write_text('\n'.join(body))
    return notes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--main', action='store_true', help='enforce G09 default cohort')
    args = parser.parse_args()
    try:
        print(json.dumps(summarize(args.directory, args.main), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'summary FAIL: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
