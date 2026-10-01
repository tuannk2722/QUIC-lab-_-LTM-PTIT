#!/usr/bin/env python3
"""Check measured P8 evidence. Nothing here fabricates kernel/network values."""
import csv
import json
from pathlib import Path
import re
import statistics
import sys


def read(path):
    return json.loads(Path(path).read_text())


def probe(path, scenario, namespace):
    text = Path(path).read_text()
    samples = [float(v) for v in re.findall(r'time=([0-9.]+) ms', text)]
    if len(samples) < 10 or not re.search(r'(?<![\d.])0% packet loss', text):
        raise ValueError('no-loss RTT probe needs >=10 replies and no losses')
    median = statistics.median(samples)
    if scenario == 'baseline' and median >= 10:
        raise ValueError(f'baseline median {median} ms >=10 ms')
    if scenario == 'rtt50-loss0' and not 40 <= median <= 60:
        raise ValueError(f'rtt50 median {median} ms outside 50±10 ms')
    record = {'scenario': scenario, 'namespace': namespace, 'samples_ms': samples,
              'sample_count': len(samples), 'median_rtt_ms': median, 'status': 'PASS'}
    Path(str(path) + '.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def netem(snap, ns):
    target = 'ifb0' if snap['network_profile'] == 'ingress-ifb' else 'eth0'
    entries = snap['observation'][ns][target]['qdisc']
    return next(q for q in entries if q['kind'] == 'netem')


def transfer(before_path, after_path, result_path):
    before, after = read(before_path), read(after_path)
    root = Path(result_path)
    with (root / 'runs.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError('expected one trial')
    run = rows[0]
    if run['success'] != 'true' or int(run['bytes_received']) != 6 * 1048576:
        raise ValueError('actual bulk trial failed or bytes differ; failed rows retained')
    with (root / 'streams.csv').open(newline='') as f:
        streams = list(csv.DictReader(f))
    if len(streams) != 6 or any(s['checksum_ok'] != 'true' or s['success'] != 'true' for s in streams):
        raise ValueError('bulk stream bytes/FIN/hash not all verified')
    for key in ('network_profile', 'scenario'):
        if run[key] != before[key] or after[key] != before[key]:
            raise ValueError(f'network {key} label mismatch')
    if run['trace_mode'] != 'evidence' or run['phase'] != 'evidence':
        raise ValueError('G08 trials must remain outside main cohort')
    for key in ('delay_each_way_ms', 'loss_downstream_pct', 'loss_upstream_pct', 'rate_mbps'):
        if float(run[key]) != before[key] or after[key] != before[key]:
            raise ValueError(f'configured {key} differs')
    if run['netem_seed'] != (str(before['netem_seed']) if before['netem_seed'] is not None else ''):
        raise ValueError('seed label mismatch')
    delta = {}
    for ns in ('qclient', 'qserver'):
        b, a = netem(before, ns), netem(after, ns)
        delta[ns] = {k: a[k] - b[k] for k in ('bytes', 'packets', 'drops', 'overlimits')}
        if delta[ns]['bytes'] <= 0 or delta[ns]['packets'] <= 0:
            raise ValueError(f'{ns} shaping counters did not increase')
        # Inspect also verified the actual filter keys/mirred destination.
        if before['network_profile'] == 'ingress-ifb':
            pattern = r'Sent (\d+) bytes (\d+) pkt'
            bs = re.findall(pattern, before['observation'][ns]['filters_text'])
            ats = re.findall(pattern, after['observation'][ns]['filters_text'])
            if len(bs) != 1 or len(ats) != 1 or int(ats[0][1]) <= int(bs[0][1]):
                raise ValueError(f'{ns} redirect action packet counter did not increase')
    if before['network_profile'] == 'ingress-ifb':
        if delta['qclient']['bytes'] < int(run['bytes_received']) or delta['qclient']['bytes'] <= 5 * delta['qserver']['bytes']:
            raise ValueError('receiver direction counter sanity failed (downstream must dominate bulk)')
        if before['loss_downstream_pct'] > 0 and delta['qclient']['drops'] <= 0:
            raise ValueError('bulk loss scenario showed no downstream drops; retain evidence and diagnose')
    rate = float(run['goodput_mbps'])
    if rate <= 0 or rate > before['rate_mbps'] * 1.1 or float(run['transfer_ms']) < 1000:
        raise ValueError(f'sustained bulk rate sanity failed: {rate} Mbps')
    record = {'run_id': run['run_id'], 'scenario': run['scenario'], 'transport': run['transport'],
              'network_profile': run['network_profile'], 'goodput_mbps': rate,
              'counter_delta': delta, 'status': 'PASS',
              'loss_note': 'Downstream is server→client IPv4, including handshake/control/ACK; drops may include queue overflow, not empirical random-loss probability.'}
    Path(str(after_path) + '.check.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def cleared(path):
    data = read(path)
    if data['verified']:
        raise ValueError('cleared snapshot still labeled verified impairment')
    for ns in ('qclient', 'qserver'):
        item = data['observation'][ns]
        if item['filters'] or any(not (q.get('root') is True and q.get('handle') == '0:'
                and (q.get('kind') == 'noqueue' or (d == 'ifb0' and q.get('kind') == 'fq_codel')))
                for d in ('eth0', 'ifb0') for q in item[d]['qdisc']):
            raise ValueError('shaping/filter remains after clear')
    return {'status': 'PASS', 'clear': str(path)}


def main():
    op, *args = sys.argv[1:]
    action = {'probe': probe, 'transfer': transfer, 'cleared': cleared}[op]
    print(json.dumps(action(*args)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, StopIteration, OSError) as error:
        print(f'G08 check FAIL: {error}', file=sys.stderr)
        sys.exit(1)
