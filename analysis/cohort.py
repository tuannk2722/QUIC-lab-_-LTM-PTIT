"""Cohort invariants and observed handshake modes. No data synthesis."""
import hashlib
import json
from itertools import permutations
from collections import Counter, defaultdict
from pathlib import Path

from validate import SCHEMA, read_csv, require, validate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


HANDSHAKE_MODES = ('cold', 'resumed', 'early')


def handshake_state(run, streams):
    """Separate transfer success from achieving the requested handshake mode.

    Early qualification uses client API state and completed REQUEST enqueue;
    packet corroboration is deliberately a separate P11 requirement.
    """
    rid = run['run_id']
    fallback = run['fallback_count']
    require(fallback in (0, 1), f'{rid}: more than one fallback')
    require(not run['attempted_0rtt'] or run['mode'] == 'early', f'{rid}: early API in another mode')
    require(run['used_0rtt'] is not True or
            (run['attempted_0rtt'] and run['tls_resumed'] is True and run['early_rejected'] is False),
            f'{rid}: contradictory accepted early state')
    require(run['early_rejected'] is not True or
            (run['attempted_0rtt'] and run['used_0rtt'] is not True), f'{rid}: contradictory rejection state')
    require(not fallback or
            (run['mode'] == 'early' and run['attempted_0rtt'] and run['early_rejected'] is True and
             run['used_0rtt'] is False), f'{rid}: fallback without actual early rejection')
    require(all(s['attempt_index'] == fallback for s in streams), f'{rid}: final attempt index differs')
    achieved = False
    classification = 'failed_transfer' if not run['success'] else 'mode_unachieved'
    if run['success']:
        if fallback:
            classification = 'fallback'
        elif run['mode'] == 'cold':
            achieved = (run['tls_resumed'] is False and run['used_0rtt'] is False and
                        not run['attempted_0rtt'] and run['early_rejected'] is not True)
            if achieved:
                classification = 'cold'
        elif run['mode'] == 'resumed':
            achieved = (run['tls_resumed'] is True and run['used_0rtt'] is False and
                        not run['attempted_0rtt'] and run['early_rejected'] is not True and
                        run['handshake_ms'] is not None and all(s['request_start_ms'] is not None and
                        run['handshake_ms'] <= s['request_start_ms'] for s in streams))
            if achieved:
                classification = 'resumed'
        elif run['mode'] == 'early':
            handshake = run['handshake_ms']
            achieved = (run['attempted_0rtt'] and run['tls_resumed'] is True and
                        run['used_0rtt'] is True and run['early_rejected'] is False and
                        handshake is not None and run['early_ready_ms'] is not None and bool(streams) and
                        all(s['request_start_ms'] is not None and run['early_ready_ms'] <= s['request_start_ms'] and
                            s['request_end_ms'] is not None and s['request_end_ms'] < handshake for s in streams))
            if achieved:
                classification = 'early_api_qualified'
    return {'mode_achieved': achieved, 'mode_classification': classification,
            'latency_eligible': run['success'] and achieved}


def handshake_schedule(plan, groups, strict=False):
    require(plan['profile'] == 'handshake' and plan['scenario_names'] == ['rtt50-loss0'],
            'handshake suite profile/scenario differs')
    profile = plan['workloads']['profiles'][plan['profile']]
    require(profile == {'resource_count': 1, 'resource_size_bytes': 1024, 'chunk_bytes': 1024},
            'handshake workload differs')
    c = next(c for c in plan['scenarios']['scenarios'] if c['name'] == 'rtt50-loss0')
    require(all(c[k] == value for k, value in [('delay_each_way_ms', 25), ('loss_downstream_pct', 0),
                                            ('loss_upstream_pct', 0), ('rate_mbps', 20)]),
            'handshake scenario differs from normative default')
    orders, seeds = defaultdict(Counter), []
    for group in groups.values():
        require(len(group) == 3 and {e['transport'] for e in group} == {'quic'} and
                {e['mode'] for e in group} == set(HANDSHAKE_MODES) and
                {e['order_index'] for e in group} == {0, 1, 2}, 'invalid handshake triple')
        group = sorted(group, key=lambda e: e['order_index'])
        require(all(group[0][k] == e[k] for e in group[1:]
                    for k in ['phase', 'repeat_index', 'scenario', 'netem_seed']), 'triple config differs')
        orders[group[0]['phase']][tuple(e['mode'] for e in group)] += 1
        seeds.append(group[0]['netem_seed'])
    nonnull = [s for s in seeds if s is not None]
    require(len(nonnull) == len(set(nonnull)), 'seed reused across handshake triples')
    for phase, count in [('warmup', plan['warmups']), ('measured', plan['runs'])]:
        observed = orders[phase]
        require(sum(observed.values()) == count, f'{phase}: wrong handshake triple count')
        require({g[0]['repeat_index'] for g in groups.values() if g[0]['phase'] == phase} == set(range(count)),
                f'{phase}: missing/duplicate handshake repeat')
        frequencies = [observed[p] for p in permutations(HANDSHAKE_MODES)]
        require(max(frequencies) - min(frequencies) <= 1, f'{phase}: handshake permutations unbalanced')
        # Full 30-triple gate is balanced at every position. A reduced
        # correctness cohort can stop partway through a permutation cycle.
        for position in range(3) if strict or count % 6 == 0 else []:
            positions = [sum(n for order, n in observed.items() if order[position] == mode)
                         for mode in HANDSHAKE_MODES]
            require(max(positions) - min(positions) <= 1, f'{phase}: handshake positions unbalanced')
    if strict:
        require(plan['execution'] == 'ingress-ifb' and plan['runs'] == 30 and plan['warmups'] == 2,
                'G10 requires ingress-ifb and 30 measured +2 target warmups per mode')


def handshake_sidecars(directory, run, streams):
    """Verify replay history and separate ticket warm-up for completed targets."""
    rid = run['run_id']
    path = directory / 'shards' / rid / 'attempts' / (rid + '.json')
    if not path.exists():
        require(not run['success'], f'{rid}: successful handshake target missing attempts')
        return
    sidecar = json.loads(path.read_text())
    require(type(sidecar['schema_version']) is int and sidecar['schema_version'] == 1 and sidecar['run_id'] == rid,
            f'{rid}: invalid attempts identity')
    require(type(sidecar['target_invoked']) is bool and type(sidecar['ticket_observed']) is bool,
            f'{rid}: invalid attempts observation types')
    attempts = sidecar['attempts']
    require(len(attempts) <= 2 and [a['attempt_index'] for a in attempts] == list(range(len(attempts))),
            f'{rid}: invalid replay history')
    require(sidecar['target_invoked'] == bool(attempts), f'{rid}: target invocation differs')
    for a in attempts:
        record = a['record']
        require(record['run']['run_id'] == rid and record['run']['mode'] == run['mode'] and
                record['run']['experiment_id'] == run['experiment_id'], f'{rid}: attempt identity differs')
        require(all(s['attempt_index'] == a['attempt_index'] for s in record['streams']),
                f'{rid}: attempt stream indexes differ')
        require(record['run']['timestamp_utc'] == run['timestamp_utc'], f'{rid}: fallback reset t0')
    if run['success']:
        require(len(attempts) == run['fallback_count'] + 1, f'{rid}: missing/extra final attempt')
        require(attempts[-1]['record'] == {'run': {k: v for k, v in run.items()
                                                if k not in ('mode_achieved', 'mode_classification', 'latency_eligible')},
                                         'streams': streams}, f'{rid}: final attempt disagrees with aggregate')
    if len(attempts) == 2:
        original = attempts[0]['record']['run']
        require(not original['success'] and original['early_rejected'] is True and
                original['used_0rtt'] is False and original['fallback_count'] == 0,
                f'{rid}: replay did not follow rejected attempt')
    if run['success'] and run['mode'] in ('resumed', 'early'):
        require(sidecar['ticket_observed'] is True, f'{rid}: target missing ticket notification')
        warmup = directory / 'shards' / rid / 'ticket-warmup'
        counts = validate(warmup)
        require(counts['attempted'] == counts['success'] == 1, f'{rid}: invalid separate ticket warm-up')
        warm = next((warmup / 'raw').glob('*.json'))
        prior = json.loads(warm.read_text())['run']
        require(prior['phase'] == 'warmup' and prior['mode'] == 'cold' and prior['transport'] == 'quic' and
                prior['experiment_id'] == run['experiment_id'] and prior['tls_resumed'] is False and
                prior['used_0rtt'] is False and all(prior[k] == run[k] for k in
                ['resource_count', 'resource_size_bytes', 'chunk_bytes']), f'{rid}: ticket warm-up state differs')


def load(directory, main=False, handshake=False):
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
            require(r['scenario'] == 'loopback-test' and r['netem_seed'] is None and
                    all(r[k] == 0 for k in ['rate_mbps', 'delay_each_way_ms', 'loss_downstream_pct', 'loss_upstream_pct']),
                    'loopback has false applied impairment')
        pairs[e['pair_id']].append(e)
    handshake_suite = plan.get('suite', 'bulk') == 'handshake'
    require(not (main and handshake), 'cannot request both G09 and G10 cohorts')
    require(not handshake or handshake_suite, 'G10 requires handshake suite')
    if handshake_suite:
        require(not main, 'G09 requires bulk suite')
        require(all(r['trace_mode'] == 'performance' for r in runs), 'mixed handshake trace mode')
        handshake_schedule(plan, pairs, handshake)
        by_run = defaultdict(list)
        for stream in streams:
            by_run[stream['run_id']].append(stream)
        for r in runs:
            group = sorted(by_run[r['run_id']], key=lambda s: s['resource_id'])
            r.update(handshake_state(r, group))
            handshake_sidecars(directory, r, group)
        if handshake:
            require(result['measured_trials'] == 90 and result['warmup_trials_excluded'] == 6 and len(streams) == 96,
                    'G10 requires 90 measured +6 target warmup and 96 stream rows')
        return runs, streams, plan, result
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
