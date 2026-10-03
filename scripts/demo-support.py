#!/usr/bin/env python3
"""Ordinary-user P12 demo records and audits, reusing P8/P11 evidence rules."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
from datetime import datetime

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'scripts'), str(REPO / 'analysis'), str(REPO / 'tests/system')]
from build import digest, load_verified
from check_g08 import netem, cleared
from check_g10 import check_kernel
from check_g11 import audit_capture
from evidence import check_progress, correlated, early_qlog, viewer, render_timeline
from hol import tcp_candidate, quic_candidate
from packet_evidence import decode, early_packet_proof, parse_pdml
from validate import require

spec = importlib.util.spec_from_file_location('demo_bench_support', REPO / 'scripts/bench-support.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
read, put, now = bench.read, bench.put, bench.now
KINDS = ('basic', 'baseline', 'loss', '0rtt')


def plan(kind, disabled=False):
    """One declared live sample; random loss selection never reruns to win."""
    if kind not in KINDS:
        raise ValueError('unknown demo kind')
    seed = None if disabled else 2026100200
    if kind == '0rtt':
        rows = [('handshake_' + mode, 'handshake', 'quic', mode, 'rtt50-loss0')
                for mode in ('cold', 'resumed', 'early')]
    elif kind == 'basic':
        rows = [('basic_quic', 'handshake', 'quic', 'cold', 'baseline')]
    else:
        scenario = 'baseline' if kind == 'baseline' else 'rtt50-loss3'
        seed = None if disabled else 2026100201
        rows = [(kind + '_' + tr, 'bulk', tr, 'cold', scenario) for tr in ('tcp', 'quic')]
    return [dict(run_id=rid, profile=profile, transport=tr, mode=mode, scenario=scenario, seed=seed)
            for rid, profile, tr, mode, scenario in rows]


def prepare(out, kind, backup=''):
    out = Path(out)
    require(out.is_absolute() and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', out.name), 'invalid absolute demo output/experiment ID')
    receipt = load_verified(REPO / 'bin/build.json')
    out.mkdir()
    for name in ('logs', 'network', 'host', 'probes', 'runs', 'traces', 'captures', 'viewers', 'config'):
        (out / name).mkdir()
    shutil.copyfile(REPO / 'bin/build.json', out / 'build.json')
    for name in ('configs/workloads.json', 'configs/scenarios.json', 'certs/server.crt', 'schemas/result-records.schema.json'):
        shutil.copyfile(REPO / name, out / 'config' / Path(name).name)
    sources = {str(p.relative_to(REPO)): digest(p)
               for name in ('internal', 'cmd', 'scripts', 'analysis', 'tests', 'configs', 'schemas')
               for p in (REPO / name).rglob('*')
               if p.is_file() and p.suffix in ('.go', '.py', '.sh', '.json', '.txt')}
    sources.update(receipt['inputs'])
    put(out / 'source-hashes.json', sources)
    put(out / 'manifest.json', dict(
        schema_version=1, experiment_id=out.name, demo=kind, scope='P12 live single-sample demo',
        trace_mode='evidence', performance_pooling=False, created_utc=now(), uid=os.getuid(), gid=os.getgid(),
        kernel=subprocess.check_output(['uname', '-a'], text=True).strip(),
        distribution=Path('/etc/os-release').read_text(), resources=Path('/proc/meminfo').read_text(),
        logical_cpus=len(os.sched_getaffinity(0)), cpu_info=Path('/proc/cpuinfo').read_text(),
        host_os='Windows 11 user-reported D13', execution_layer='Ubuntu WSL2',
        wsl_version='unknown: Windows CLI not queried', build=receipt,
        decoder=subprocess.check_output(['bash', str(REPO / 'scripts/tshark.sh'), '-v'], text=True),
        planned_runs=plan(kind, os.environ.get('NETEM_SEED') == 'none'), runs=[],
        config_sha256={p.name: digest(p) for p in (out / 'config').iterdir()},
        capture_points='paired qclient/qserver eth0; receiver tap may precede ingress IFB; reception uses ACK/SACK or qlog',
        argv=sys.argv, timeout_seconds=60, watchdog_seconds=135,
        backup=backup, attempt_policy='one declared sample; all attempts retained; no superiority requirement; HOL can remain INCONCLUSIVE'))


def invocation(out, rid, code):
    out = Path(out)
    manifest = read(out / 'manifest.json')
    planned = next(r for r in manifest['planned_runs'] if r['run_id'] == rid)
    matches = [r for r in manifest['runs'] if r['run_id'] == rid]
    if code == 'pending':
        require(not matches, 'duplicate demo invocation')
        manifest['runs'].append(dict(**planned, exit_code=None, started_utc=now(), ended_utc=None,
                                   out='runs/' + rid, client_qlog='traces/' + rid + '/client-qlog',
                                   server_qlog='traces/server-qlog', client_keylog='traces/' + rid + '/client.keylog',
                                   server_keylog='traces/server.keylog', captures='captures/' + rid))
    else:
        require(len(matches) == 1 and matches[0]['exit_code'] is None, 'demo completion mismatch')
        matches[0].update(exit_code=int(code), ended_utc=now())
    put(out / 'manifest.json', manifest)


def network(out, entry, record):
    rid = entry['run_id']
    before, after = [read(out / 'network' / (rid + '.' + label + '.json')) for label in ('before', 'after')]
    scenario = next(s for s in read(out / 'config/scenarios.json')['scenarios'] if s['name'] == entry['scenario'])
    for state in (before, after):
        check_kernel(state)
        require(state['scenario'] == entry['scenario'] and state['netem_seed'] == entry['seed'], 'demo network/seed differs')
        require(state['config_sha256'] == digest(out / 'config/scenarios.json'), 'network config hash differs')
        for key in ('delay_each_way_ms', 'loss_downstream_pct', 'loss_upstream_pct', 'rate_mbps'):
            require(state[key] == scenario[key] == record['run'][key], 'network parameters differ: ' + key)
    for key in ('client_namespace_id', 'server_namespace_id', 'config_sha256', 'seed_status'):
        require(before[key] == after[key], 'network changed during trial: ' + key)
    run = record['run']
    require(run['network_profile'] == 'ingress-ifb' and run['scenario'] == entry['scenario'] and
            run['netem_seed'] == entry['seed'], 'raw applied network labels differ')
    delta = {}
    for ns in ('qclient', 'qserver'):
        b, a = netem(before, ns), netem(after, ns)
        values = {k: a[k] - b[k] for k in ('bytes', 'packets', 'drops', 'overlimits')}
        require(all(v >= 0 for v in values.values()), 'counters reset during demo')
        counts = [re.findall(r'Sent (\d+) bytes (\d+) pkt', state['observation'][ns]['filters_text'])
                  for state in (before, after)]
        require(all(len(c) == 1 for c in counts), 'redirect counters unavailable')
        values['redirect_packets'] = int(counts[1][0][1]) - int(counts[0][0][1])
        if run['success']:
            require(values['packets'] > 0 and values['redirect_packets'] > 0, 'missing IFB/redirect traffic')
        delta[ns] = values
    if run['success'] and entry['profile'] == 'bulk':
        require(delta['qclient']['bytes'] >= run['bytes_received'] and
                delta['qclient']['bytes'] > 5 * delta['qserver']['bytes'], 'bulk direction sanity failed')
        require(0 < run['goodput_mbps'] <= scenario['rate_mbps'] * 1.1, 'bulk rate sanity failed')
        if scenario['loss_downstream_pct']:
            require(delta['qclient']['drops'] > 0, 'loss sample has no actual downstream drops')
    idle_files = sorted((out / 'network').glob(rid + '.idle-*-before.json'),
                        key=lambda p: int(p.name.split('.idle-')[1].split('-')[0]))
    require(idle_files and [int(p.name.split('.idle-')[1].split('-')[0]) for p in idle_files] == list(range(len(idle_files))),
            'idle observation inventory differs')
    previous = datetime.fromisoformat(after['timestamp_utc'])
    for path in idle_files:
        for state in (read(path), read(path.with_name(path.name.replace('-before', '-after')))):
            check_kernel(state)
            for key in ('scenario', 'netem_seed', 'config_sha256', 'client_namespace_id', 'server_namespace_id'):
                require(state[key] == before[key], 'idle identity/config changed')
            stamp = datetime.fromisoformat(state['timestamp_utc'])
            require(stamp >= previous, 'idle chronology reversed')
            previous = stamp
    bench.idle(idle_files[-1], idle_files[-1].with_name(idle_files[-1].name.replace('-before', '-after')))
    require(datetime.fromisoformat(before['timestamp_utc']) <= datetime.fromisoformat(run['timestamp_utc']) <=
            datetime.fromisoformat(entry['ended_utc']) <= datetime.fromisoformat(after['timestamp_utc']), 'trial chronology differs')
    delta['accepted_idle_utc'] = previous.isoformat()
    return delta


def backup_evidence(path, review_path=None):
    if not path:
        return dict(status='UNAVAILABLE', label='pre-recorded', reason='no accepted G11 root supplied')
    root = Path(path).resolve()
    check = read(root / 'g11-check.json')
    require(check['status'] == check['hol'] == check['early_proof'] == 'PASS' and
            check['full_demo_complete'] is True, 'backup is not accepted complete G11 evidence')
    require(check['counts'] == dict(n_planned=23, n_invoked=23, n_success=23, n_failed=0), 'backup G11 denominator differs')
    hashes = check['artifact_sha256']
    require(hashes, 'backup artifact hashes missing')
    exception = None
    for name, expected in hashes.items():
        artifact = (root / name).resolve()
        require(artifact.is_relative_to(root), 'unsafe backup artifact path')
        actual = digest(artifact)
        if actual != expected:
            # Accepted G11 has exactly one recorded self-log timing defect.
            # Match the independently reviewed completed bytes and original
            # receipt; no other path/hash mismatch is exempted.
            review_file = Path(review_path) if review_path else REPO / 'docs/evidence/p11/g11-rerun-review.json'
            review = read(review_file)
            audit = review['original_public_hash_audit']
            prefix = review['actual_root']
            require(review['status'] == 'PASS' and root.name == Path(prefix).name and
                    audit['recorded_count'] == len(hashes) and audit['matching'] == len(hashes) - 1 and
                    len(audit['exceptions']) == 1, 'backup hash mismatch has no exact closure audit')
            item = audit['exceptions'][0]
            inventory = review['archive']['inventory']
            require(name == item['path'] == 'logs/check.log' and
                    expected == item['recorded_sha256'] == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' and
                    actual == item['actual_sha256'] == inventory[prefix + '/logs/check.log']['sha256'] and
                    artifact.stat().st_size == item['bytes'] and
                    digest(root / 'g11-check.json') == inventory[prefix + '/g11-check.json']['sha256'],
                    'backup artifact changed: ' + name)
            exception = dict(path=name, completed_sha256=actual, review_sha256=digest(review_file))
    return dict(status='PASS', label='pre-recorded', root=str(root), representative=check['representative'],
                early_run_id='handshake_early', receipt_sha256=digest(root / 'g11-check.json'),
                reviewed_self_log_exception=exception)


def audit_run(out, entry, uid, readonly=False):
    rid = entry['run_id']
    record, rows = check_progress(out / entry['out'])
    run = record['run']
    require(run['phase'] == run['trace_mode'] == 'evidence' and run['run_id'] == rid and
            run['mode'] == entry['mode'] and run['transport'] == entry['transport'], 'demo raw labels differ')
    require(entry['exit_code'] in (0, 1) and (entry['exit_code'] == 0) == run['success'], 'demo exit/transfer mismatch')
    expected = (1, 1024, 1024) if entry['profile'] == 'handshake' else (6, 1048576, 16384)
    require(tuple(run[k] for k in ('resource_count', 'resource_size_bytes', 'chunk_bytes')) == expected, 'demo workload differs')
    result = dict(run_id=rid, status='PASS' if run['success'] else 'FAIL', success=run['success'],
                  transport=run['transport'], mode=run['mode'], profile=entry['profile'], raw=entry['out'] + '/raw/' + rid + '.json',
                  bytes_received=run['bytes_received'], total_ms=run['total_ms'], used_0rtt=run['used_0rtt'],
                  tls_resumed=run['tls_resumed'], early_rejected=run['early_rejected'], fallback_count=run['fallback_count'],
                  progress_points=len(rows), network=network(out, entry, record))
    pairs = correlated(out / entry['client_qlog'], out / entry['server_qlog'], rid) if run['transport'] == 'quic' else []
    if run['success'] and run['transport'] == 'quic':
        require(len(pairs) == (1 if run['mode'] == 'cold' else 2), 'demo qlog connection count differs')
    if not readonly:
        viewer(out / 'viewers' / (rid + '.html'), pairs, rows, rid)
        render_timeline(out / 'viewers' / (rid + '.png'), pairs, rows, rid)
    result['viewer'] = 'viewers/' + rid + '.html'
    decoded = {}
    for ns in ('qclient', 'qserver'):
        cap = audit_capture(out, entry, ns, uid)
        for key in ('client_keylog', 'server_keylog'):
            require((out / entry[key]).stat().st_mode & 0o777 == 0o600, 'keylog permissions differ')
        if readonly:
            decoded[ns] = parse_pdml(cap / 'decoded/packets.pdml')
            require(decoded[ns] == read(cap / 'decoded/packets.json'), 'saved decoded packets differ from decoder PDML')
        else:
            decoded[ns] = decode(cap / 'capture.pcap', out / entry['client_keylog'], cap / 'decoded')
        for packet in decoded[ns]:
            packet['capture_namespace'] = ns
    packets = sorted([p for values in decoded.values() for p in values], key=lambda p: p['epoch'])
    if run['transport'] == 'quic':
        require(any(p.get('quic') and p['packet_type'] == 0 for p in packets) and
                any(p.get('quic') and p['packet_number'] is not None and p['streams'] for p in packets), 'QUIC UDP/decryption unavailable')
        result['udp_decode'] = 'PASS'
        if run['mode'] == 'early':
            api = early_qlog(pairs, record)
            target = next(p for p in pairs if p['role'] == 'target')
            result['early_qlog'] = api
            result['early_packet'] = {ns: early_packet_proof(values, target, record, api) for ns, values in decoded.items()}
            result['early_proof'] = 'PASS' if all(p['status'] == 'PASS' for p in result['early_packet'].values()) else 'INCONCLUSIVE'
        elif run['success']:
            require(run['tls_resumed'] is (run['mode'] == 'resumed') and run['used_0rtt'] is False and
                    run['attempted_0rtt'] is False, 'cold/resumed actual API state differs')
        if entry['scenario'] == 'rtt50-loss3':
            result['hol'] = quic_candidate(next(p for p in pairs if p['role'] == 'target'), record, rows)
    else:
        require(any(p['protocol'] == 'tcp' and p['length'] > 0 for p in packets), 'TCP capture empty')
        if entry['scenario'] == 'rtt50-loss3':
            result['hol'] = tcp_candidate(packets, record, rows)
    return result


def evaluate(out, original, cleanup, readonly=False):
    out = Path(out)
    manifest = read(out / 'manifest.json')
    results, errors = [], []
    host = {}
    for kind in ('link', 'address', 'route'):
        try:
            host[kind] = all((out / 'host' / (kind + '.before.json')).read_bytes() ==
                             (out / 'host' / (kind + '.' + label + '.json')).read_bytes() for label in ('active', 'final'))
        except OSError as exc:
            host[kind] = False
            errors.append(str(exc))
    cleanup_record = dict(original_exit=int(original), cleanup_exit=int(cleanup), host_unchanged=host, finished_utc=now())
    try:
        require(manifest['uid'] > 0 and manifest['trace_mode'] == 'evidence' and manifest['performance_pooling'] is False,
                'demo UID/trace/cohort labels differ')
        require(read(out / 'build.json') == manifest['build'], 'demo receipt/manifest differs')
        require(all(read(out / 'source-hashes.json').get(k) == h for k, h in manifest['build']['inputs'].items()), 'demo source/receipt differs')
        for name, expected in manifest['config_sha256'].items():
            require(digest(out / 'config' / name) == expected, 'archived config changed')
        require(manifest['planned_runs'] and manifest['planned_runs'] ==
                plan(manifest['demo'], manifest['planned_runs'][0]['seed'] is None), 'demo plan differs')
        require([{k: r[k] for k in ('run_id', 'profile', 'transport', 'mode', 'scenario', 'seed')} for r in manifest['runs']] ==
                manifest['planned_runs'][:len(manifest['runs'])], 'demo invocation order differs')
        require(int(cleanup) == 0 and all(host.values()), 'demo cleanup/host state failed')
        cleared(out / 'network/cleanup.json')
        for scenario in ('baseline', 'rtt50-loss0'):
            check_kernel(read(out / 'network' / (scenario + '-probe.json')))
            for ns in ('qclient', 'qserver'):
                # Recheck raw probe without changing recorded summaries.
                path = out / 'probes' / (scenario + '-' + ns + '.log')
                previous = read(str(path) + '.json')
                text = path.read_text()
                samples = [float(v) for v in re.findall(r'time=([0-9.]+) ms', text)]
                require(samples == previous['samples_ms'] and previous['status'] == 'PASS', 'probe summary differs')
                median = statistics.median(samples)
                require(previous == dict(scenario=scenario, namespace=ns, samples_ms=samples,
                                         sample_count=len(samples), median_rtt_ms=median, status='PASS'), 'probe summary differs')
                require(len(samples) >= 10 and re.search(r'(?<![\d.])0% packet loss', text) and
                        (median < 10 if scenario == 'baseline' else 40 <= median <= 60), 'RTT probes failed')
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        errors.append(str(exc))
    last_idle = None
    for entry in manifest['runs']:
        try:
            result = audit_run(out, entry, manifest['uid'], readonly)
            before_stamp = datetime.fromisoformat(read(out / 'network' / (entry['run_id'] + '.before.json'))['timestamp_utc'])
            require(last_idle is None or last_idle <= before_stamp, 'demo reset before prior accepted idle')
            last_idle = datetime.fromisoformat(result['network']['accepted_idle_utc'])
        except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.SubprocessError) as exc:
            raw = out / entry['out'] / 'raw' / (entry['run_id'] + '.json')
            try:
                observed = read(raw)['run']['success'] if raw.exists() else None
            except (OSError, ValueError, KeyError, TypeError):
                observed = None
            result = dict(run_id=entry['run_id'], status='FAIL', success=observed, transport=entry['transport'], error=str(exc))
            errors.append(entry['run_id'] + ': ' + str(exc))
        results.append(result)
    backup = dict(status='UNAVAILABLE', label='pre-recorded')
    try:
        backup = backup_evidence(manifest['backup'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        backup['reason'] = str(exc)
    counts = dict(n_planned=len(manifest['planned_runs']), n_invoked=len(manifest['runs']),
                  n_success=sum(r['success'] is True for r in results), n_failed=sum(r['success'] is not True for r in results),
                  n_missing=len(manifest['planned_runs']) - len(manifest['runs']))
    proof = dict(udp_decode='PASS' if any(r.get('udp_decode') == 'PASS' for r in results) else 'NOT_PROVED',
                 early='NOT_APPLICABLE', hol='NOT_APPLICABLE')
    if manifest['demo'] == '0rtt':
        proof['early'] = next((r.get('early_proof', 'INCONCLUSIVE') for r in results if r.get('mode') == 'early'), 'NOT_PROVED')
        if proof['early'] != 'PASS':
            errors.append('accepted 0RTT REQUEST not demonstrated; retain actual fallback/rejection state')
    if manifest['demo'] == 'loss':
        proof['hol'] = 'PASS' if len(results) == 2 and all(r.get('hol', {}).get('status') == 'PASS' for r in results) else 'INCONCLUSIVE'
        if proof['hol'] != 'PASS' and backup['status'] != 'PASS':
            errors.append('live HOL inconclusive and no verified pre-recorded G11 backup')
    passed = int(original) == int(cleanup) == 0 and not errors and counts['n_missing'] == counts['n_failed'] == 0
    status = dict(schema_version=1, demo=manifest['demo'], status='PASS' if passed else 'FAIL',
                  scope='actual live ingress IFB sample; instrumented and excluded from performance cohorts',
                  counts=counts, proof=proof, cleanup=cleanup_record, runs=results, errors=errors, backup=backup,
                  manifest_sha256=digest(out / 'manifest.json'), finished_utc=now())
    return status


def public_artifacts(out):
    # check.log is still open while finish runs through launch-log. G12 binds
    # its completed log separately; avoid the known G11 SHA256(empty) defect.
    return {str(p.relative_to(out)): digest(p) for p in out.rglob('*')
            if p.is_file() and p.suffix != '.keylog' and p.name not in ('demo-check.json', 'demo.json')
            and str(p.relative_to(out)) != 'logs/check.log'}


def verify(out):
    """Read-only replay for G12; no raw, viewer, decoder or summary rewrites."""
    out = Path(out).resolve()
    saved = read(out / 'demo-check.json')
    require(saved['status'] == 'PASS' and saved['artifact_sha256'], 'saved demo is not a complete PASS')
    owner = read(out / 'manifest.json')['uid']
    require(all(p.stat().st_uid == owner and p.resolve().is_relative_to(out) for p in out.rglob('*') if p.is_file()),
            'demo artifact ownership/path differs')
    require(saved['artifact_sha256'] == public_artifacts(out), 'demo public artifacts changed')
    require(saved['manifest_sha256'] == digest(out / 'manifest.json'), 'demo manifest changed')
    cleanup = read(out / 'cleanup.json')
    # Causal witnesses contain Python tuples (SACK edges/progress points).
    # Compare their canonical JSON representation to the persisted receipt.
    replay = json.loads(json.dumps(evaluate(out, cleanup['original_exit'], cleanup['cleanup_exit'], readonly=True), allow_nan=False))
    for key in ('demo', 'status', 'scope', 'counts', 'proof', 'runs', 'errors', 'backup', 'manifest_sha256'):
        require(replay[key] == saved[key], 'demo replay differs: ' + key)
    require(cleanup['host_unchanged'] == replay['cleanup']['host_unchanged'], 'cleanup host summary differs')
    require(read(out / 'demo.json') == {k: v for k, v in saved.items() if k not in ('runs', 'artifact_sha256')}, 'compact demo summary differs')
    return dict(status='PASS', demo=saved['demo'], counts=saved['counts'], proof=saved['proof'],
                readonly=True, check_sha256=digest(out / 'demo-check.json'))


def finish(out, original, cleanup):
    out = Path(out)
    status = evaluate(out, original, cleanup)
    put(out / 'cleanup.json', status['cleanup'])
    status['artifact_sha256'] = public_artifacts(out)
    put(out / 'demo-check.json', status)
    put(out / 'demo.json', {k: v for k, v in status.items() if k not in ('runs', 'artifact_sha256')})
    print(json.dumps({k: v for k, v in status.items() if k not in ('runs', 'artifact_sha256')}, indent=2))
    for result in status['runs']:
        print('Demo:', result['run_id'], 'transfer=' + str(result['success']),
              'total_ms=' + str(result.get('total_ms')), 'Used0RTT=' + str(result.get('used_0rtt')),
              'fallback=' + str(result.get('fallback_count')), 'viewer=' + str(result.get('viewer')))
    if status['proof']['hol'] == 'INCONCLUSIVE':
        print('HOL: INCONCLUSIVE in this one live pair. Completion timelines alone do not prove causality.')
        print('Pre-recorded backup:', status['backup'])
    return 0 if status['status'] == 'PASS' else 1


def main():
    if os.getuid() == 0:
        raise ValueError('demo files and analysis must run as the ordinary owner')
    op, *args = sys.argv[1:]
    if op == 'prepare':
        prepare(*args)
    elif op == 'run':
        invocation(*args)
    elif op == 'finish':
        return finish(*args)
    elif op == 'verify':
        print(json.dumps(verify(*args), indent=2))
    elif op == 'list':
        for row in read(Path(args[0]) / 'manifest.json')['planned_runs']:
            print('\t'.join(str(row[k]) if row[k] is not None else 'none'
                            for k in ('run_id', 'profile', 'transport', 'mode', 'scenario', 'seed')))
    else:
        raise ValueError('unknown demo operation')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.SubprocessError) as exc:
        print('demo support:', exc, file=sys.stderr)
        sys.exit(1)
