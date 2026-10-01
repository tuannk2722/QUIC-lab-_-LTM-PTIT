#!/usr/bin/env python3
"""Export actual CSV points/boxplots with units, success n and failed counts."""
import argparse
import json
import os
import sys
from pathlib import Path

from cohort import load

# Use project-local pinned packages and font cache. No GUI/network needed.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / '.tools/analysis'))
os.environ.setdefault('MPLCONFIGDIR', str(REPO / '.tools/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot(directory, main=False):
    runs, streams, plan, _ = load(directory, main)
    plots = directory / 'plots'
    plots.mkdir(exist_ok=True)
    measured = [r for r in runs if r['phase'] == 'measured']
    scenarios = list(dict.fromkeys(r['scenario'] for r in measured))
    colors = {'tcp': '#2563eb', 'quic': '#d97706'}
    files = []
    def finish(fig, name):
        fig.tight_layout()
        for extension in ['svg', 'png']:
            path = plots / f'{name}.{extension}'
            fig.savefig(path, dpi=150)
            files.append(str(path.relative_to(directory)))
        plt.close(fig)
    for metric, unit in [('total_ms', 'ms'), ('ttfa_ms', 'ms'), ('goodput_mbps', 'Mbit/s')]:
        fig, ax = plt.subplots(figsize=(max(7, len(scenarios)*3), 5))
        labels = []
        pos = 0
        for scenario in scenarios:
            for transport in ['tcp', 'quic']:
                pos += 1
                group = [r for r in measured if r['scenario'] == scenario and r['transport'] == transport]
                success = [r for r in group if r['success']]
                values = [r[metric] for r in success if r[metric] is not None]
                if values:
                    ax.boxplot([values], positions=[pos], widths=.5, showfliers=False)
                    # Deterministic point offsets expose all observations, including outliers.
                    offsets = [pos + ((i % 7)-3)*.025 for i in range(len(values))]
                    ax.scatter(offsets, values, c=colors[transport], alpha=.7, s=15)
                labels.append(f"{scenario}\n{transport}\nn={len(success)}/{len(group)}, fail={len(group)-len(success)}")
        ax.set_xticks(range(1, pos+1), labels, fontsize=8)
        ax.set_ylabel(f'{metric} ({unit})')
        ax.set_title(f"{plan['experiment_id']} — successful measured trials\n{plan['execution']}; warmups excluded")
        ax.grid(axis='y', alpha=.2)
        finish(fig, metric)
    by_run = {r['run_id']: r for r in measured}
    fig, axes = plt.subplots(max(1, len(scenarios)), 1, figsize=(10, max(4, len(scenarios)*3.5)), squeeze=False)
    count = plan['workloads']['profiles'][plan['profile']]['resource_count']
    for scenario, ax in zip(scenarios, axes[:, 0]):
        for resource in range(1, count+1):
            for transport, shift in [('tcp', -.16), ('quic', .16)]:
                group = [r for r in measured if r['scenario'] == scenario and r['transport'] == transport]
                values = [s['complete_ms'] for s in streams if s['resource_id'] == resource and s['run_id'] in by_run
                          and by_run[s['run_id']]['scenario'] == scenario and by_run[s['run_id']]['transport'] == transport
                          and by_run[s['run_id']]['success'] and s['success'] and s['complete_ms'] is not None]
                if values:
                    ax.scatter([resource+shift+((i%5)-2)*.015 for i in range(len(values))], values, c=colors[transport], alpha=.55, s=12)
        info = []
        for tr in ['tcp', 'quic']:
            g = [r for r in measured if r['scenario'] == scenario and r['transport'] == tr]
            n = sum(r['success'] for r in g)
            info.append(f'{tr}: n={n}/{len(g)}, fail={len(g)-n}')
        ax.set_title(f"{scenario} — {'; '.join(info)}")
        ax.set_xticks(range(1, count+1))
        ax.set_xlabel('Resource ID (correlated within each run)')
        ax.set_ylabel('complete_ms (ms)')
        ax.grid(axis='y', alpha=.2)
    finish(fig, 'resource-completion')
    record = {'source': ['runs.csv', 'streams.csv'], 'files': files, 'matplotlib': matplotlib.__version__,
              'scope': 'successful measured trials with failures labeled; no HOL causal claim; progress evidence belongs to P11'}
    (plots / 'index.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--main', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(plot(args.directory, args.main), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'plots FAIL: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
