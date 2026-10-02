#!/usr/bin/env python3
"""P10 actual-state/ticket/attempt checker; packet proof remains G11 work."""
import csv
import importlib.util
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'analysis'))
sys.path.insert(0, str(REPO / 'scripts'))
from cohort import digest, load
from summarize import HANDSHAKE_COLUMNS, summarize_rows
from validate import SCHEMA, require, validate, validate_raw_record, validate_session_state, validate_timeline

spec = importlib.util.spec_from_file_location('g10_network_state', REPO / 'scripts/network/state.py')
network_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(network_state)

INFRASTRUCTURE_ERRORS = {'environment_error', 'not_started', 'missing_shard', 'interrupted',
                         'result_write_error', 'runner_error'}


def read(path):
    return json.loads(Path(path).read_text())


def check_kernel(snapshot):
    """Revalidate saved observations with the same pure rules as live inspect."""
    require(snapshot['verified'] is True and snapshot['network_profile'] == 'ingress-ifb', 'unverified main kernel snapshot')
    expected_seed_status = 'disabled-explicitly' if snapshot['netem_seed'] is None else 'requested-and-verified'
    require(snapshot['seed_status'] == expected_seed_status, 'kernel seed status differs')
    try:
        for ns in ('qclient', 'qserver'):
            item = snapshot['observation'][ns]
            require(item['namespace_id'] == snapshot['client_namespace_id' if ns == 'qclient' else 'server_namespace_id'],
                    'saved namespace identity differs')
            for dev, kind in (('eth0', 'veth'), ('ifb0', 'ifb')):
                links = [link for link in item['link'] if link['ifname'] == dev]
                require(len(links) == 1 and links[0]['linkinfo']['info_kind'] == kind and
                        'UP' in links[0]['flags'] and links[0]['mtu'] == snapshot['mtu'], 'kernel interface/MTU differs')
                qdiscs = item[dev]['qdisc']
                netems = [q for q in qdiscs if q['kind'] == 'netem']
                require(len(netems) == (1 if dev == 'ifb0' else 0), 'missing/duplicate/egress main shaping')
                require(all(network_state.default_qdisc(q, dev) or
                            (dev == 'ifb0' and q['kind'] == 'netem' and q['handle'] == '1:' and q.get('root') is True) or
                            (dev == 'eth0' and q['kind'] == 'ingress' and q['handle'] == 'ffff:') for q in qdiscs),
                        'unexpected kernel qdisc/placement')
                if netems:
                    network_state.verify_netem(netems[0], snapshot, ns)
                network_state.check_offloads(item[dev]['offloads'], f'{ns}/{dev}')
            require(sum(q['kind'] == 'ingress' for q in item['eth0']['qdisc']) == 1, 'missing/duplicate ingress redirect')
            network_state.check_filters(item['filters'], ns)
    except network_state.NetworkError as exc:
        raise ValueError('saved kernel verification: ' + str(exc)) from exc


def check_host_and_probes(root, cleanup):
    require(cleanup['original_exit'] in (0, 1) and cleanup['cleanup_exit'] == 0 and
            cleanup['environment_failed'] is False and
            cleanup['host_unchanged'] == dict(link=True, address=True, route=True), 'cleanup/host summary failed')
    for kind in ('link', 'address', 'route'):
        before = (root / 'host' / (kind + '.before.json')).read_bytes()
        require(all(before == (root / 'host' / (kind + '.' + label + '.json')).read_bytes()
                    for label in ('active', 'final')), 'raw host snapshot changed: ' + kind)
    expected_paths = {scenario + '-' + ns + '.log.json' for scenario in ('baseline', 'rtt50-loss0')
                      for ns in ('qclient', 'qserver')}
    require({p.name for p in (root / 'probes').glob('*.log.json')} == expected_paths, 'RTT probe set differs')
    for scenario in ('baseline', 'rtt50-loss0'):
        for ns in ('qclient', 'qserver'):
            path = root / 'probes' / (scenario + '-' + ns + '.log')
            raw = path.read_text()
            samples = [float(value) for value in re.findall(r'time=([0-9.]+) ms', raw)]
            require(len(samples) >= 10 and re.search(r'(?<![\d.])0% packet loss', raw), 'raw no-loss RTT replies absent')
            median = statistics.median(samples)
            require(median < 10 if scenario == 'baseline' else 40 <= median <= 60, 'raw RTT tolerance failed')
            expected = dict(scenario=scenario, namespace=ns, samples_ms=samples, sample_count=len(samples),
                            median_rtt_ms=median, status='PASS')
            require(read(str(path) + '.json') == expected, 'RTT summary differs from raw probe')


def check_warmup(trial, target, ticket_observed):
    path = trial / 'ticket-warmup'
    counts = validate(path)
    require(counts['attempted'] == 1, 'ticket warm-up must contain one separate trial')
    records = list((path / 'raw').glob('*.json'))
    require(len(records) == 1, 'extra/missing ticket warm-up raw')
    prior = read(records[0])['run']
    check_warmup_record(prior, target, ticket_observed, counts)
    return counts


def check_idle(root, rid, support):
    """Keep transient failed checks, but require a saved quiet pair at the end."""
    after = read(root / 'network' / (rid + '.after.json'))
    last = datetime.fromisoformat(after['timestamp_utc'])
    pairs = sorted((root / 'network').glob(rid + '.idle-*-before.json'),
                   key=lambda p: int(p.name.removeprefix(rid + '.idle-').removesuffix('-before.json')))
    require(1 <= len(pairs) <= 50, 'missing/unbounded idle checks')
    quiet = False
    for index, before_path in enumerate(pairs):
        require(before_path.name == rid + f'.idle-{index}-before.json', 'idle check sequence differs')
        after_path = before_path.with_name(rid + f'.idle-{index}-after.json')
        before, final = read(before_path), read(after_path)
        for item in (before, final):
            check_kernel(item)
            require(all(item[k] == after[k] for k in ('scenario', 'netem_seed', 'config_sha256',
                        'client_namespace_id', 'server_namespace_id')), 'idle network identity changed')
        btime, atime = [datetime.fromisoformat(v['timestamp_utc']) for v in (before, final)]
        require(last <= btime <= atime, 'idle snapshots out of order')
        last = atime
        try:
            support.idle(before_path, after_path)
            quiet = True
        except ValueError:
            quiet = False
        require(not quiet or index == len(pairs)-1, 'unexpected checks after quiet success')
    require(quiet, 'saved network never became quiet')
    return last


def check_warmup_record(prior, target, ticket_observed, counts):
    expected_id = target['run_id'] + '_ticket'
    if len(expected_id) > 128:
        expected_id = 'ticket_warmup'
    require(prior['run_id'] == expected_id and prior['experiment_id'] == target['experiment_id'] and
            prior['phase'] == 'warmup' and prior['mode'] == 'cold' and prior['transport'] == 'quic' and
            not prior['attempted_0rtt'] and prior['tls_resumed'] is not True and prior['used_0rtt'] is not True,
            'ticket warm-up identity/state differs')
    require(all(prior[k] == target[k] for k in ('resource_count', 'resource_size_bytes', 'chunk_bytes', 'scenario',
                'network_profile', 'trace_mode', 'repeat_index', 'pair_id', 'order_index', 'delay_each_way_ms',
                'loss_downstream_pct', 'loss_upstream_pct', 'rate_mbps', 'netem_seed')), 'ticket warm-up cohort differs')
    require(datetime.fromisoformat(prior['timestamp_utc']) < datetime.fromisoformat(target['timestamp_utc']),
            'ticket warm-up did not precede target')
    if ticket_observed:
        require(counts['success'] == 1 and prior['tls_resumed'] is False and prior['used_0rtt'] is False,
                'observed ticket preparation failed')


def check_functional_layout(name, run, counts):
    require(counts['attempted'] == 1, 'functional case must contain exactly one target: ' + name)
    require(run['run_id'] == name and run['resource_count'] == (6 if name == 'rejected' else 1) and
            run['resource_size_bytes'] == run['chunk_bytes'] == 1024 and run['transport'] == 'quic' and
            run['network_profile'] == 'loopback-test', 'functional identity/workload differs: ' + name)


def qualified(run, streams):
    if not run['success'] or run['fallback_count'] != 0:
        return False
    if run['mode'] == 'cold':
        return run['tls_resumed'] is False and run['used_0rtt'] is False and not run['attempted_0rtt']
    if run['mode'] == 'resumed':
        return run['tls_resumed'] is True and run['used_0rtt'] is False and not run['attempted_0rtt']
    return (run['tls_resumed'] is True and run['used_0rtt'] is True and run['attempted_0rtt'] and
            run['early_rejected'] is False and run['early_ready_ms'] is not None and
            run['handshake_ms'] is not None and all(s['request_start_ms'] is not None and
                s['request_end_ms'] is not None and s['request_end_ms'] < run['handshake_ms'] for s in streams))


def check_history(history, final):
    rid = final['run']['run_id']
    require(history['schema_version'] == 1 and history['run_id'] == rid and
            type(history['ticket_observed']) is bool and type(history['target_invoked']) is bool, 'invalid history binding/types')
    attempts = history['attempts']
    require(type(attempts) is list and len(attempts) <= 2 and
            history['target_invoked'] == bool(attempts), 'invalid attempt count/target invocation')
    definitions = read(SCHEMA)['$defs']
    for index, a in enumerate(attempts):
        require(type(a['attempt_index']) is int and a['attempt_index'] == index, 'duplicate/out-of-order attempts')
        record = a['record']
        r, streams = record['run'], record['streams']
        validate_raw_record(r, definitions['run'], rid)
        require(r['run_id'] == rid and r['experiment_id'] == final['run']['experiment_id'] and
                r['timestamp_utc'] == final['run']['timestamp_utc'], 'attempt reset t0/identity')
        require(all(r[k] == final['run'][k] for k in ('mode', 'transport', 'resource_count', 'resource_size_bytes',
                    'chunk_bytes', 'scenario', 'network_profile', 'trace_mode')), 'attempt changed workload/cohort')
        require(len(streams) == r['resource_count'] and {s['resource_id'] for s in streams} ==
                set(range(1, r['resource_count']+1)), 'attempt resource slots')
        validate_session_state(r, streams)
        for s in streams:
            validate_raw_record(s, definitions['stream'], rid)
            validate_timeline(r, s)
            require(s['run_id'] == rid and s['experiment_id'] == r['experiment_id'] and s['attempt_index'] == index,
                    'attempt stream identity/index')
            require(s['bytes_received'] <= s['bytes_expected'], 'attempt payload overflow')
        require(r['bytes_received'] == sum(s['bytes_received'] for s in streams), 'attempt bytes counted twice')
    if attempts:
        require(attempts[-1]['record'] == final, 'last history differs from final raw')
    if len(attempts) == 2:
        first, last = [a['record'] for a in attempts]
        require(not first['run']['success'] and first['run']['early_rejected'] is True and
                first['run']['fallback_count'] == 0 and last['run']['fallback_count'] == 1, 'invalid replay transition')
        require(all(s['request_start_ms'] is None or s['request_start_ms'] >= first['run']['elapsed_ms']
                    for s in last['streams']), 'fallback started before old workers stopped')


def check_functional(root):
    root = Path(root)
    paths = ['cold', 'resumed', 'early', 'rejected', 'missing_ticket', 'target_handshake_failure', 'target_cancel']
    counts = {}
    for name in paths:
        trial = root / name
        counts[name] = validate(trial)
        raw_paths = list((trial / 'raw').glob('*.json'))
        require(len(raw_paths) == 1, 'extra/missing functional raw: ' + name)
        record = read(raw_paths[0])
        r, streams = record['run'], record['streams']
        check_functional_layout(name, r, counts[name])
        history = read(trial / 'attempts' / (r['run_id'] + '.json'))
        check_history(history, record)
        if name in ('cold', 'resumed', 'early'):
            require(qualified(r, streams), 'functional mode was not achieved: ' + name)
        elif name == 'rejected':
            require(r['success'] and r['tls_resumed'] is True and r['used_0rtt'] is False and
                    r['early_rejected'] is True and r['fallback_count'] == 1 and r['bytes_received'] == 6144,
                    'forced rejection did not preserve valid resumption/one replay/bytes')
            require([a['attempt_index'] for a in history['attempts']] == [0, 1], 'duplicate/missing fallback attempts')
            first, last = [a['record'] for a in history['attempts']]
            require(first['run']['timestamp_utc'] == last['run']['timestamp_utc'] == r['timestamp_utc'], 'fallback reset t0')
            require(not first['run']['success'] and last['run']['success'], 'attempt states invalid')
            require(all(s['attempt_index'] == 1 for s in streams), 'old stream attempt leaked into final rows')
        else:
            require(not r['success'] and r['fallback_count'] == 0, 'negative trial pretended success/replayed')
            if name == 'missing_ticket':
                require(not history['target_invoked'] and not history['ticket_observed'] and not history['attempts'],
                        'missing ticket invoked target')
                require(r['error_code'] == 'timeout', 'missing ticket classification')
        if name != 'cold':
            check_warmup(trial, r, history['ticket_observed'])
        else:
            require(history['ticket_observed'] is False and not (trial / 'ticket-warmup').exists(), 'functional cold used ticket preparation')
        if name in ('resumed', 'early', 'rejected'):
            require(history['ticket_observed'] and history['target_invoked'], 'valid ticket signal absent')
    status = dict(status='PASS', scope='actual localhost correctness, no performance or packet proof', cases=counts)
    (root / 'functional-check.json').write_text(json.dumps(status, indent=2) + '\n')
    return status


def check(root, software=False):
    root = Path(root)
    require((root / 'build.json').is_file() and 'build.json' in read(root / 'manifest.json')['hashes'], 'G10 requires build provenance receipt')
    runs, streams, plan, counts = load(root)
    require(plan['suite'] == 'handshake' and plan['profile'] == 'handshake' and plan['runs'] == 30 and plan['warmups'] == 2,
            'G10 needs default three-mode 30+2 schedule')
    require(plan['scenario_names'] == ['rtt50-loss0'] and len(runs) == len(streams) == 96 and
            counts['measured_trials'] == 90 and counts['warmup_trials_excluded'] == 6, 'handshake cohort count differs')
    require(plan['execution'] == ('loopback-test' if software else 'ingress-ifb'), 'wrong execution profile')
    require(read(root / 'manifest.json')['session_policy']['fresh_cache_per_sequence'], 'session policy absent')
    merge_record = read(root / 'merge.json')
    merge = merge_record['counts']
    require(merge['n_invoked'] == 96 and merge['n_missing_shards'] == 0 and
            merge['n_success'] + merge['n_failed'] == merge['n_attempted'] == 96, 'invocations/denominator incomplete')
    achieved, failures, fallback = Counter(), Counter(), Counter()
    entries = {e['run_id']: e for e in plan['entries']}
    require([r['run_id'] for r in runs] == [e['run_id'] for e in plan['entries']], 'aggregate schedule order differs')
    last_idle = None
    ticket_warmups = 0
    require(set(merge_record['sources']) == {r['run_id'] for r in runs}, 'merge source set differs')
    require(all(r['error_code'] not in INFRASTRUCTURE_ERRORS for r in runs), 'G10 infrastructure/runner incomplete dataset')
    for r in runs:
        rid, mode = r['run_id'], r['mode']
        shard = root / 'shards' / rid
        require(read(root / 'logs' / (rid + '.claim.json')) == entries[rid], 'atomic claim differs from entry')
        inv = read(root / 'logs' / (rid + '.invocation.json'))
        require(inv['schema_version'] == 1 and inv['run_id'] == rid and type(inv['exit_code']) is int and
                0 <= inv['exit_code'] <= 255 and datetime.fromisoformat(inv['ended_utc']) >= datetime.fromisoformat(inv['started_utc']),
                'unfinished invocation')
        require(not r['success'] or inv['exit_code'] == 0, 'success with nonzero exit')
        raw_path = shard / 'raw' / (rid + '.json')
        source = merge_record['sources'][rid]
        require(source['raw'] == str(raw_path.relative_to(root)) and source['sha256'] == digest(raw_path), 'merged shard provenance differs')
        final_record = read(raw_path)
        require(final_record == read(root / 'raw' / (rid + '.json')), 'aggregate differs from completed source shard')
        history = read(shard / 'attempts' / (rid + '.json'))
        check_history(history, final_record)
        require(history['run_id'] == rid and len(history['attempts']) <= 2, 'invalid/unbounded attempt history')
        group = [s for s in streams if s['run_id'] == rid]
        if mode != 'cold':
            ticket_warmups += 1
            check_warmup(shard, r, history['ticket_observed'])
            if r['success']:
                require(history['ticket_observed'] and history['target_invoked'], 'ticket wait missing')
        else:
            require(not history['ticket_observed'] and not (shard / 'ticket-warmup').exists(), 'cold has prior ticket')
        if r['success']:
            info = read(shard / 'connection.json')
            require(info['tls_version'] == 'TLS 1.3' and info['alpn'] == 'quicbench/1' and info['quic_version'] == 'v1', 'actual TLS/QUIC differs')
            require(info['did_resume'] == r['tls_resumed'] and info['used_0rtt'] == r['used_0rtt'], 'raw/API state differs')
        if r['phase'] == 'measured':
            achieved[mode] += int(qualified(r, group))
            failures[mode] += int(not r['success'])
            fallback[mode] += int(r['fallback_count'] == 1)
        if not software:
            require(read(root / 'network' / (rid + '.check.json'))['status'] == 'PASS', 'network verification failed')
            for side in ('before', 'after'):
                check_kernel(read(root / 'network' / (rid + '.' + side + '.json')))
            # Re-run the parser/counter checks on the actual saved snapshots.
            spec = importlib.util.spec_from_file_location('bench_support', REPO / 'scripts/bench-support.py')
            support = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(support)
            before_time = datetime.fromisoformat(read(root / 'network' / (rid + '.before.json'))['timestamp_utc'])
            after_time = datetime.fromisoformat(read(root / 'network' / (rid + '.after.json'))['timestamp_utc'])
            require((last_idle is None or last_idle <= before_time) and
                    before_time <= datetime.fromisoformat(inv['started_utc']) <=
                    datetime.fromisoformat(inv['ended_utc']) <= after_time, 'network/invocation chronology differs')
            require(support.check_network(root, rid, publish=False) ==
                    read(root / 'network' / (rid + '.check.json'))['details'], 'saved network counter check differs')
            last_idle = check_idle(root, rid, support)
    require(ticket_warmups == 64, 'ticket warmups missing/pooled')
    for mode in ('cold', 'resumed', 'early'):
        require(sum(r['phase'] == 'measured' and r['mode'] == mode for r in runs) == 30, 'mode repeat count differs')
        require(achieved[mode] > 0, 'no API-qualified actual mode: ' + mode)
    expected = summarize_rows(runs, handshake=True)
    with (root / 'summary.csv').open(newline='') as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames == HANDSHAKE_COLUMNS, 'summary header differs')
        actual = list(reader)
    require(actual == [{k: '' if row[k] is None else str(row[k]) for k in HANDSHAKE_COLUMNS} for row in expected], 'summary not CSV-derived')
    plots = read(root / 'plots/index.json')
    require(plots['files'] and all((root / p).stat().st_size > 1000 for p in plots['files']), 'plots missing/empty')
    if not software:
        cleanup = read(root / 'cleanup.json')
        check_host_and_probes(root, cleanup)
        require(read(root / 'runtime.json')['uid'] > 0, 'root application')
    artifacts = {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file() and p.name != 'g10-check.json'}
    status = dict(gate='G10-suite', status='PASS', scope='localhost correctness' if software else 'actual ingress IFB handshake cohort',
                  counts=counts, api_qualified_measured=dict(achieved), failures=dict(failures), fallback=dict(fallback),
                  ticket_warmups_separate=ticket_warmups, artifact_sha256=artifacts,
                  packet_proof='NOT_RUN: P11 required; API/timing alone is not full accepted-early evidence')
    (root / 'g10-check.json').write_text(json.dumps(status, indent=2) + '\n')
    return {k: v for k, v in status.items() if k != 'artifact_sha256'}


if __name__ == '__main__':
    try:
        root = Path(sys.argv[1])
        print(json.dumps(check_functional(root) if '--functional' in sys.argv[2:] else check(root, '--software' in sys.argv[2:]), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, AssertionError) as exc:
        print('G10 check FAIL:', exc, file=sys.stderr)
        sys.exit(1)
