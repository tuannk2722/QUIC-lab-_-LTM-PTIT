#!/usr/bin/env python3
"""Export actual CSV points/boxplots with units, success n and failed counts."""
import argparse
import json
import os
import sys
from pathlib import Path

from cohort import HANDSHAKE_MODES, load

# Use project-local pinned packages and font cache. No GUI/network needed.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / '.tools/analysis'))
os.environ.setdefault('MPLCONFIGDIR', str(REPO / '.tools/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot_groups(measured, handshake=False):
    """Keep QUIC handshake modes as distinct statistical trial groups."""
    scenarios = list(dict.fromkeys(r['scenario'] for r in measured))
    kinds = [('quic', m) for m in HANDSHAKE_MODES] if handshake else [('tcp', 'cold'), ('quic', 'cold')]
    return [(scenario, transport, mode, [r for r in measured if r['scenario'] == scenario and
             r['transport'] == transport and r['mode'] == mode])
            for scenario in scenarios for transport, mode in kinds]


def plot(directory, main=False, handshake=False):
    runs, streams, plan, _ = load(directory, main, handshake)
    handshake_suite = plan.get('suite', 'bulk') == 'handshake'
    plots = directory / 'plots'
    plots.mkdir(exist_ok=True)
    measured = [r for r in runs if r['phase'] == 'measured']
    scenarios = list(dict.fromkeys(r['scenario'] for r in measured))
    colors = {'tcp': '#2563eb', 'quic': '#d97706', 'cold': '#2563eb', 'resumed': '#d97706', 'early': '#16803a'}
    groups = plot_groups(measured, handshake_suite)
    def eligible(row):
        return row['success'] and (not handshake_suite or row['latency_eligible'])
    def label(scenario, transport, mode, group):
        success = sum(r['success'] for r in group)
        text = f"{scenario}\n{mode if handshake_suite else transport}\nn={success}/{len(group)}, fail={len(group)-success}"
        if handshake_suite:
            text += f"\nmode={sum(r['mode_achieved'] for r in group)}, fallback={sum(r['fallback_count'] > 0 for r in group)}"
        return text
    files = []
    def finish(fig, name):
        fig.tight_layout()
        for extension in ['svg', 'png']:
            path = plots / f'{name}.{extension}'
            fig.savefig(path, dpi=150)
            files.append(str(path.relative_to(directory)))
        plt.close(fig)
    metrics = [('handshake_ms', 'ms'), ('ttfa_ms', 'ms'), ('total_ms', 'ms')] if handshake_suite else [
        ('total_ms', 'ms'), ('ttfa_ms', 'ms'), ('goodput_mbps', 'Mbit/s')]
    for metric, unit in metrics:
        fig, ax = plt.subplots(figsize=(max(9 if handshake_suite else 7, len(scenarios)*3), 5))
        labels = []
        pos = 0
        for scenario, transport, mode, group in groups:
            pos += 1
            values = [r[metric] for r in group if eligible(r) and r[metric] is not None]
            if values:
                ax.boxplot([values], positions=[pos], widths=.5, showfliers=False)
                # Deterministic offsets expose all observations, including outliers.
                offsets = [pos + ((i % 7)-3)*.025 for i in range(len(values))]
                ax.scatter(offsets, values, c=colors[mode if handshake_suite else transport], alpha=.7, s=15)
            labels.append(label(scenario, transport, mode, group))
        ax.set_xticks(range(1, pos+1), labels, fontsize=8)
        ax.set_ylabel(f'{metric} ({unit})')
        if handshake_suite:
            ax.set_title(f"{plan['experiment_id']} — requested mode achieved\n"
                         f"Early API qualification; packet proof in separate evidence\n{plan['execution']}; warmups excluded", fontsize=10)
        else:
            ax.set_title(f"{plan['experiment_id']} — successful measured trials\n{plan['execution']}; warmups excluded")
        ax.grid(axis='y', alpha=.2)
        finish(fig, metric)
    by_run = {r['run_id']: r for r in measured}
    fig, axes = plt.subplots(max(1, len(scenarios)), 1, figsize=(10, max(4, len(scenarios)*3.5)), squeeze=False)
    count = plan['workloads']['profiles'][plan['profile']]['resource_count']
    for scenario, ax in zip(scenarios, axes[:, 0]):
        for resource in range(1, count+1):
            kinds = [('quic', mode, shift) for mode, shift in zip(HANDSHAKE_MODES, [-.24, 0, .24])] if handshake_suite else [
                ('tcp', 'cold', -.16), ('quic', 'cold', .16)]
            for transport, mode, shift in kinds:
                values = [s['complete_ms'] for s in streams if s['resource_id'] == resource and s['run_id'] in by_run
                          and by_run[s['run_id']]['scenario'] == scenario and by_run[s['run_id']]['transport'] == transport
                          and by_run[s['run_id']]['mode'] == mode and eligible(by_run[s['run_id']]) and
                          s['success'] and s['complete_ms'] is not None]
                if values:
                    ax.scatter([resource+shift+((i%5)-2)*.015 for i in range(len(values))], values,
                               c=colors[mode if handshake_suite else transport], alpha=.55, s=12,
                               label=mode if handshake_suite else transport)
        info = []
        for name, transport, mode, group in groups:
            if name == scenario:
                info.append(label('', transport, mode, group).strip().replace('\n', ': ', 1).replace('\n', ', '))
        if handshake_suite:
            ax.set_title(f"{scenario}\n" + '\n'.join(info), fontsize=9)
        else:
            ax.set_title(f"{scenario} — {'; '.join(info)}")
        ax.set_xticks(range(1, count+1))
        ax.set_xlabel('Resource ID (correlated within each run)')
        ax.set_ylabel('complete_ms (ms)')
        ax.grid(axis='y', alpha=.2)
        if handshake_suite and ax.collections:
            ax.legend(title='Mode (API qualification)', fontsize=8)
    finish(fig, 'resource-completion')
    record = {'source': ['runs.csv', 'streams.csv'], 'files': files, 'matplotlib': matplotlib.__version__,
              'scope': 'successful measured trials with failures labeled; no HOL causal claim; progress evidence belongs to P11'}
    if handshake_suite:
        record.update(scope='requested mode achieved; transfer failures/fallback counted; early API-qualified only, packet corroboration belongs to separate evidence',
                      groups=[{'scenario': scenario, 'transport': transport, 'mode': mode,
                               'n_attempted': len(group), 'n_success': sum(r['success'] for r in group),
                               'n_failed': sum(not r['success'] for r in group),
                               'n_mode_achieved': sum(r['mode_achieved'] for r in group),
                               'n_fallback': sum(r['fallback_count'] > 0 for r in group)}
                              for scenario, transport, mode, group in groups])
    (plots / 'index.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--main', action='store_true')
    parser.add_argument('--handshake', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(plot(args.directory, args.main, args.handshake), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'plots FAIL: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
