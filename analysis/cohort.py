"""P9 cohort invariants shared by summary/plots/gate checker. No data synthesis."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from validate import SCHEMA, read_csv, require, validate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(directory, main=False):
    directory = Path(directory)
    result = validate(directory)
    definitions = json.loads(SCHEMA.read_text())["$defs"]
    runs = read_csv(directory / 'runs.csv', definitions['run'])
    streams = read_csv(directory / 'streams.csv', definitions['stream'])
    plan = json.loads((directory / 'schedule.json').read_text())
    entries = plan['entries']
    by_id = {e['run_id']: e for e in entries}
    require(len(by_id) == len(entries) == len(runs), 'schedule/run count or duplicate mismatch')
    require(set(by_id) == {r['run_id'] for r in runs}, 'scheduled entries missing/extra')
    require({p.stem for p in (directory / 'raw').glob('*.json')} == set(by_id), 'extra/missing aggregate raw')
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(manifest['experiment_id'] == plan['experiment_id'], 'manifest experiment mismatch')
    require(manifest['hashes']['schedule.json'] == digest(directory / 'schedule.json'), 'schedule hash differs')
    # Historical P9 artifacts predate build receipts. New receipts are bound
    # to both the manifest and the saved source inventory, not today's tree.
    if 'build.json' in manifest['hashes']:
        receipt = json.loads((directory / 'build.json').read_text())
        require(digest(directory / 'build.json') == manifest['hashes']['build.json'], 'build receipt hash differs')
        require(receipt == manifest['build_provenance'], 'manifest/build receipt differs')
        sources = json.loads((directory / 'source-hashes.json').read_text())
        require(receipt['schema_version'] == 1 and set(receipt['binaries']) == {'server', 'client', 'bench'}, 'invalid build receipt')
        require(all(sources.get(k) == v for k, v in receipt['inputs'].items()), 'build/source inventory differs')
    for name, field, embedded in [('workloads.json', 'workloads_sha256', 'workloads'),
                                   ('scenarios.json', 'scenarios_sha256', 'scenarios'), ('ca.crt', 'ca_sha256', None)]:
        path = directory / 'config' / name
        require(digest(path) == plan[field], 'saved config/CA hash differs')
        if embedded:
            require(json.loads(path.read_text()) == plan[embedded], 'embedded configuration differs')
    profile = plan['workloads']['profiles'][plan['profile']]
    scenarios = {c['name']: c for c in plan['scenarios']['scenarios']}
    pairs = defaultdict(list)
    for r in runs:
        e = by_id[r['run_id']]
        require(r['experiment_id'] == plan['experiment_id'], 'mixed experiment')
        for key in ['phase', 'repeat_index', 'pair_id', 'order_index', 'transport', 'mode', 'trace_mode']:
            require(r[key] == e[key], f"{r['run_id']}: schedule {key} mismatch")
        for key in ['resource_count', 'resource_size_bytes', 'chunk_bytes']:
            require(r[key] == profile[key], 'mixed workload')
        require(r['network_profile'] == plan['execution'], 'mixed execution profile')
        if plan['execution'] == 'ingress-ifb':
            require(r['scenario'] == e['scenario'] and r['netem_seed'] == e['netem_seed'], 'scenario/seed mismatch')
            for key in ['delay_each_way_ms', 'loss_downstream_pct', 'loss_upstream_pct', 'rate_mbps']:
                require(r[key] == scenarios[e['scenario']][key], 'mixed scenario configuration')
        else:
            require(r['scenario'] == 'loopback-test' and r['netem_seed'] is None and r['rate_mbps'] == 0,
                    'loopback has false applied impairment')
        pairs[e['pair_id']].append(e)
    order = Counter()
    seeds = []
    for group in pairs.values():
        require(len(group) == 2 and {e['transport'] for e in group} == {'tcp', 'quic'} and
                {e['order_index'] for e in group} == {0, 1}, 'invalid transport pair')
        group.sort(key=lambda e: e['order_index'])
        require(all(group[0][k] == group[1][k] for k in ['phase', 'repeat_index', 'scenario', 'netem_seed']), 'pair config differs')
        order[group[0]['scenario'], group[0]['phase'], group[0]['transport']] += 1
        seeds.append(group[0]['netem_seed'])
    nonnull = [s for s in seeds if s is not None]
    require(len(nonnull) == len(set(nonnull)), 'seed reused across repeats')
    for scenario in plan['scenario_names']:
        for phase in ['warmup', 'measured']:
            require(abs(order[scenario, phase, 'tcp'] - order[scenario, phase, 'quic']) <= 1, 'AB/BA unbalanced')
    if main:
        require(plan['execution'] == 'ingress-ifb' and plan['profile'] == 'bulk' and
                profile == {'resource_count': 6, 'resource_size_bytes': 1048576, 'chunk_bytes': 16384}, 'main workload/profile differs')
        require(plan['runs'] == 30 and plan['warmups'] == 2 and set(plan['scenario_names']) ==
                {'baseline', 'rtt50-loss0', 'rtt50-loss1', 'rtt50-loss3'}, 'main schedule differs')
        require(result['measured_trials'] == 240 and result['warmup_trials_excluded'] == 16 and len(streams) == 1536,
                'main requires 240 measured +16 warmup and 1536 stream rows')
        require(all(r['mode'] == 'cold' and r['trace_mode'] == 'performance' for r in runs), 'mixed main trace/mode')
        for name,delay,loss in [('baseline',0,0),('rtt50-loss0',25,0),('rtt50-loss1',25,1),('rtt50-loss3',25,3)]:
            c = scenarios[name]
            require(c['delay_each_way_ms'] == delay and c['loss_downstream_pct'] == loss and
                    c['loss_upstream_pct'] == 0 and c['rate_mbps'] == 20, 'main scenario differs from normative default')
    return runs, streams, plan, result
