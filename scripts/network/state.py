#!/usr/bin/env python3
"""P8 kernel state, not a benchmark scheduler. Called under the ownership lock.

Subprocesses receive argument lists. Only fixed lab interfaces are mutated.
Raw tc JSON is retained alongside human tc output (including queue statistics).
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

STATE = Path('/run/quic-performance-lab/impairment-v1.json')
NAMES = ('qclient', 'qserver')
FEATURES = ('tcp-segmentation-offload', 'generic-segmentation-offload',
            'generic-receive-offload', 'tx-udp-segmentation',
            'rx-udp-gro-forwarding', 'rx-gro-list')


class NetworkError(Exception):
    pass


def command(args):
    p = subprocess.run(args, text=True, capture_output=True, timeout=15)
    if p.returncode:
        raise NetworkError(f'{args!r} exit={p.returncode}: {p.stderr.strip()}')
    return p.stdout


def nscommand(ns, *args):
    return command(['ip', 'netns', 'exec', ns, *map(str, args)])


def tc(ns, *args):
    return nscommand(ns, 'tc', *args)


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate key {key}')
        result[key] = value
    return result


def load_json(path):
    with Path(path).open('rb') as f:
        raw = f.read((1 << 20) + 1)
    if len(raw) > 1 << 20:
        raise ValueError('JSON exceeds 1 MiB')
    obj = json.loads(raw, object_pairs_hook=unique,
                     parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    def depth(value, level=0):
        if level > 32:
            raise ValueError('JSON nesting exceeds 32')
        if isinstance(value, (dict, list)):
            for v in (value.values() if isinstance(value, dict) else value):
                depth(v, level + 1)
    depth(obj)
    return obj, hashlib.sha256(raw).hexdigest()


def bounded(value, lo, hi, integer=False):
    if type(value) not in (int, float) or (integer and type(value) is not int):
        raise ValueError('wrong numeric type')
    if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError('numeric value out of bounds')


def scenario_config(path, name):
    # Same JSON/bounds as internal/config.LoadScenarios; no scenario numeric copy.
    cfg, digest = load_json(path)
    keys = {'schema_version', 'default_network_profile', 'mtu', 'queue_limit_packets',
            'main_runs_per_transport', 'warmups_per_transport', 'base_seed', 'scenarios'}
    if type(cfg) is not dict or set(cfg) != keys:
        raise ValueError('unknown/missing scenario config keys')
    if type(cfg['schema_version']) is not int or cfg['schema_version'] != 1 or cfg['default_network_profile'] != 'ingress-ifb' or cfg['mtu'] != 1500:
        raise ValueError('unsupported scenario schema/profile/MTU')
    for key, lo, hi in [('queue_limit_packets', 1, 1000000),
                        ('main_runs_per_transport', 1, 100000),
                        ('warmups_per_transport', 0, 100000), ('base_seed', 0, 2**64-1)]:
        bounded(cfg[key], lo, hi, True)
    if type(cfg['scenarios']) is not list or not cfg['scenarios']:
        raise ValueError('scenarios must be a nonempty list')
    seen, selected = set(), None
    skeys = {'name', 'main_suite', 'delay_each_way_ms', 'loss_downstream_pct',
             'loss_upstream_pct', 'rate_mbps'}
    for item in cfg['scenarios']:
        if type(item) is not dict or set(item) != skeys:
            raise ValueError('unknown/missing scenario keys')
        if type(item['name']) is not str or not item['name'] or item['name'] in seen or type(item['main_suite']) is not bool:
            raise ValueError('invalid/duplicate scenario name or main_suite')
        seen.add(item['name'])
        for k, lo, hi in [('delay_each_way_ms', 0, 3600000),
                          ('loss_downstream_pct', 0, 100), ('loss_upstream_pct', 0, 100),
                          ('rate_mbps', 0, 1000000)]:
            bounded(item[k], lo, hi)
        if item['rate_mbps'] <= 0:
            raise ValueError('rate must be positive')
        if item['name'] == name:
            selected = item
    if selected is None:
        raise ValueError(f'unknown scenario {name}')
    return cfg, selected, digest


def identity(ns):
    st = os.stat('/run/netns/' + ns)
    return f'{st.st_dev}:{st.st_ino}'


def qdiscs(ns, dev):
    return json.loads(tc(ns, '-j', '-s', 'qdisc', 'show', 'dev', dev))


def features(text):
    return {m[0]: {'enabled': m[1] == 'on', 'fixed': bool(m[2])}
            for m in re.findall(r'^\s*([\w-]+): (on|off)( \[fixed\])?', text, re.M)}


def prepare_offloads():
    report = {}
    for ns in NAMES:
        report[ns] = {}
        for dev in ('eth0', 'ifb0'):
            before = nscommand(ns, 'ethtool', '-k', dev)
            parsed = features(before)
            changes = []
            for feature in FEATURES:
                status = parsed.get(feature)
                if status is None or status['fixed'] or not status['enabled']:
                    changes.append({'feature': feature, 'status': 'absent' if status is None else 'fixed' if status['fixed'] else 'already-off'})
                    continue
                try:
                    out = nscommand(ns, 'ethtool', '-K', dev, feature, 'off')
                    changes.append({'feature': feature, 'status': 'requested-off', 'output': out})
                except NetworkError as error:
                    changes.append({'feature': feature, 'status': 'failed', 'error': str(error)})
            after = nscommand(ns, 'ethtool', '-k', dev)
            report[ns][dev] = {'before': before, 'after': after, 'changes': changes}
            try:
                check_offloads(after, f'{ns}/{dev}')
            except NetworkError:
                print(json.dumps({'offload_preparation_failed': report}), file=sys.stderr)
                raise
    return report


def check_offloads(text, label):
    state = features(text)
    for feature in FEATURES:
        if feature in state and state[feature]['enabled']:
            raise NetworkError(f'{label}: {feature} remains enabled; cannot verify measurement profile')


def default_qdisc(q, dev):
    # Handle zero is kernel-assigned, not a user-installed shaping handle.
    # WSL's queued IFB uses fq_codel; veth normally uses noqueue.
    return (q.get('handle') == '0:' and q.get('root') is True
            and (q.get('kind') == 'noqueue'
                 or (dev == 'ifb0' and q.get('kind') == 'fq_codel')))


def check_clearable():
    # Refuse foreign qdiscs even in owned namespaces. Known handles survive a
    # partial apply/SIGKILL and can be explicitly cleared without a state file.
    for ns in NAMES:
        for dev in ('eth0', 'ifb0'):
            for q in qdiscs(ns, dev):
                if default_qdisc(q, dev):
                    continue
                if q['kind'] == 'netem' and q['handle'] == '1:' and q.get('root'):
                    continue
                if dev == 'eth0' and q['kind'] == 'ingress' and q['handle'] == 'ffff:':
                    filters = json.loads(tc(ns, '-j', 'filter', 'show', 'dev', dev, 'parent', 'ffff:'))
                    check_filters(filters, ns, allow_empty=True)
                    continue
                raise NetworkError(f'refusing foreign qdisc {ns}/{dev}: {q}')


def clear():
    check_clearable()  # All resources checked before the first deletion.
    for ns in NAMES:
        for dev in ('eth0', 'ifb0'):
            for q in qdiscs(ns, dev):
                if q['kind'] == 'ingress':
                    tc(ns, 'qdisc', 'del', 'dev', dev, 'ingress')
                elif q['kind'] == 'netem':
                    tc(ns, 'qdisc', 'del', 'dev', dev, 'root')
    STATE.unlink(missing_ok=True)


def check_filters(filters, ns, allow_empty=False):
    source, dest = ('10.10.0.2', '10.10.0.1') if ns == 'qclient' else ('10.10.0.1', '10.10.0.2')
    concrete = []
    for f in filters:
        if f.get('kind') != 'flower' or f.get('protocol') != 'ip' or f.get('pref') != 10:
            raise NetworkError(f'{ns}: unexpected ingress filter {f}')
        options = f.get('options', {})
        if not options:  # tc also emits a classifier header without handle/options.
            continue
        keys = options.get('keys', {})
        actions = options.get('actions', [])
        if set(keys) - {'eth_type', 'src_ip', 'dst_ip'} or keys.get('eth_type', 'ipv4') != 'ipv4' or options.get('indev'):
            raise NetworkError(f'{ns}: unexpected protocol/port/extra filter restriction')
        if keys.get('src_ip', '').removesuffix('/32') != source or keys.get('dst_ip', '').removesuffix('/32') != dest or len(actions) != 1:
            raise NetworkError(f'{ns}: filter does not select exact lab IPv4 direction')
        a = actions[0]
        if a.get('kind') != 'mirred' or a.get('to_dev') != 'ifb0' or a.get('mirred_action') != 'redirect' or a.get('direction') != 'egress':
            raise NetworkError(f'{ns}: filter action is not egress redirect to ifb0')
        concrete.append(f)
    if len(concrete) != 1 and not (allow_empty and not concrete):
        raise NetworkError(f'{ns}: expected exactly one redirect filter')


def verify_netem(q, state, ns):
    options = q.get('options', {})
    loss = state['loss_downstream_pct'] if (ns == 'qclient') == (state['network_profile'] == 'ingress-ifb') else state['loss_upstream_pct']
    expected = {'limit': state['queue_limit_packets'], 'delay': state['delay_each_way_ms'] / 1000,
                'rate': state['rate_mbps'] * 1000000 / 8}
    for key, val in expected.items():
        actual = options.get(key, 0)
        if key in ('rate', 'delay') and isinstance(actual, dict):
            actual = actual.get(key, 0)
        if not math.isclose(actual, val, rel_tol=1e-6, abs_tol=1e-8):
            raise NetworkError(f'{ns}: actual {key}={actual!r} differs from configured {val}')
    actual_loss = options.get('loss-random', {}).get('loss', 0)
    if not math.isclose(actual_loss, loss / 100, rel_tol=1e-5, abs_tol=1e-8):
        raise NetworkError(f'{ns}: random loss direction/config differs')
    if state['netem_seed'] is not None and options.get('seed') != state['netem_seed']:
        raise NetworkError(f'{ns}: requested seed not reported by kernel/tc; no silent fallback')
    if any(k in options for k in ('loss-state', 'loss-gemodel', 'slot', 'duplicate', 'reorder', 'corrupt')) or options.get('gap', 0) or options.get('delay', {}).get('jitter', 0) or options.get('ecn', False):
        raise NetworkError(f'{ns}: unexpected additional impairment')


def snapshot(state=None):
    observed = {}
    for ns in NAMES:
        item = {'namespace_id': identity(ns), 'link': json.loads(command(['ip', '-n', ns, '-j', '-d', 'link', 'show'])),
                'address': json.loads(command(['ip', '-n', ns, '-j', 'address', 'show'])),
                'tcp_cc': nscommand(ns, 'sysctl', '-n', 'net.ipv4.tcp_congestion_control').strip()}
        for dev, kind in [('eth0', 'veth'), ('ifb0', 'ifb')]:
            link = next((v for v in item['link'] if v['ifname'] == dev), None)
            if link is None or link.get('linkinfo', {}).get('info_kind') != kind or 'UP' not in link['flags']:
                raise NetworkError(f'{ns}/{dev}: actual interface kind/up state differs')
        for dev in ('eth0', 'ifb0'):
            item[dev] = {'qdisc': qdiscs(ns, dev),
                         'qdisc_text': tc(ns, '-s', '-d', 'qdisc', 'show', 'dev', dev),
                         'offloads': nscommand(ns, 'ethtool', '-k', dev)}
        ingress = any(q['kind'] == 'ingress' for q in item['eth0']['qdisc'])
        item['filters'] = json.loads(tc(ns, '-j', '-s', 'filter', 'show', 'dev', 'eth0', 'parent', 'ffff:')) if ingress else []
        item['filters_text'] = tc(ns, '-s', '-d', 'filter', 'show', 'dev', 'eth0', 'parent', 'ffff:') if ingress else ''
        if state is not None:
            if identity(ns) != state['client_namespace_id' if ns == 'qclient' else 'server_namespace_id']:
                raise NetworkError(f'{ns}: namespace changed since apply')
            target = 'ifb0' if state['network_profile'] == 'ingress-ifb' else 'eth0'
            for dev in ('eth0', 'ifb0'):
                entries = item[dev]['qdisc']
                nets = [q for q in entries if q['kind'] == 'netem']
                if len(nets) != (1 if dev == target else 0):
                    raise NetworkError(f'{ns}/{dev}: missing/duplicate shaping')
                for q in entries:
                    valid = default_qdisc(q, dev) or q['kind'] == 'netem' or (dev == 'eth0' and q['kind'] == 'ingress' and q['handle'] == 'ffff:' and target == 'ifb0')
                    if not valid:
                        raise NetworkError(f'{ns}/{dev}: unexpected qdisc {q["kind"]}')
                if nets:
                    if nets[0]['handle'] != '1:' or not nets[0].get('root'):
                        raise NetworkError(f'{ns}/{dev}: unexpected netem handle/placement')
                    verify_netem(nets[0], state, ns)
                check_offloads(item[dev]['offloads'], f'{ns}/{dev}')
            if state['network_profile'] == 'ingress-ifb':
                check_filters(item['filters'], ns)
            elif ingress or item['filters']:
                raise NetworkError(f'{ns}: egress-demo still has ingress redirect')
        observed[ns] = item
    result = dict(state or {})
    result.update(schema_version=1, verified=state is not None,
                  timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(), observation=observed)
    return result


def save_state(state):
    fd, name = tempfile.mkstemp(prefix='.impairment-', dir=STATE.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(state, f)
        os.replace(name, STATE)
    finally:
        Path(name).unlink(missing_ok=True)


def apply(args):
    cfg, item, digest = scenario_config(args.scenarios, args.scenario)
    seed = cfg['base_seed'] if args.seed == 'default' else None if args.seed == 'none' else int(args.seed)
    if seed is not None:
        bounded(seed, 0, 2**64-1, True)
    state = {k: v for k, v in item.items() if k not in ('name', 'main_suite')}
    state.update(schema_version=1, network_profile=args.profile, scenario=item['name'],
                 queue_limit_packets=cfg['queue_limit_packets'], mtu=cfg['mtu'], netem_seed=seed,
                 seed_status='requested-and-verified' if seed is not None else 'disabled-explicitly',
                 config_sha256=digest, client_namespace_id=identity('qclient'), server_namespace_id=identity('qserver'))
    try:
        clear()  # Profile changes are reset, never combined.
        state['offload_preparation'] = prepare_offloads()
        target = 'ifb0' if args.profile == 'ingress-ifb' else 'eth0'
        for ns in NAMES:
            loss = state['loss_downstream_pct'] if (ns == 'qclient') == (target == 'ifb0') else state['loss_upstream_pct']
            opts = ['qdisc', 'add', 'dev', target, 'root', 'handle', '1:', 'netem', 'limit', cfg['queue_limit_packets'],
                    'delay', f'{state["delay_each_way_ms"]}ms', 'loss', 'random', f'{loss}%', 'rate', f'{state["rate_mbps"]}mbit']
            if seed is not None:
                opts += ['seed', seed]
            if ns == 'qserver' and os.environ.get('QUICLAB_FAIL_NETEM_AFTER') == 'client':
                # Gate-only fault: real tc parser error after one receiver was
                # configured, so rollback is exercised without fake traffic.
                opts[opts.index('limit') + 1] = 'invalid-g08-limit'
            tc(ns, *opts)
            if args.profile == 'ingress-ifb':
                tc(ns, 'qdisc', 'add', 'dev', 'eth0', 'handle', 'ffff:', 'ingress')
                src, dst = ('10.10.0.2', '10.10.0.1') if ns == 'qclient' else ('10.10.0.1', '10.10.0.2')
                tc(ns, 'filter', 'add', 'dev', 'eth0', 'parent', 'ffff:', 'protocol', 'ip', 'pref', '10', 'flower',
                   'src_ip', src + '/32', 'dst_ip', dst + '/32', 'action', 'mirred', 'egress', 'redirect', 'dev', 'ifb0')
        result = snapshot(state)  # A successful tc exit alone cannot publish a verified state.
        save_state(state)
        return result
    except BaseException:
        try:
            clear()
        except Exception as error:
            print(f'network: rollback failed: {error}', file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='operation', required=True)
    p = subs.add_parser('apply')
    p.add_argument('--scenario', required=True)
    p.add_argument('--scenarios', default='configs/scenarios.json')
    p.add_argument('--profile', choices=('ingress-ifb', 'egress-demo'), default='ingress-ifb')
    p.add_argument('--seed', default='default', help='uint64, default (config base_seed), or none (explicit limitation)')
    subs.add_parser('clear')
    subs.add_parser('inspect')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise NetworkError('requires the root ownership-checked shell wrapper')
    # Keep direct invocation subject to the same owner/identity requirement.
    marker = STATE.parent / 'topology-v1'
    fields = marker.read_text().splitlines()
    if len(fields) != 5 or fields[:3] != ['quic-lab-topology-v1', os.environ.get('SUDO_UID'), os.environ.get('SUDO_GID')] or fields[1] == '0' or fields[3:] != [identity(ns) for ns in NAMES]:
        raise NetworkError('ownership marker/caller/namespace mismatch')
    for path, mode in [(STATE.parent, 0o700), (marker, 0o600)]:
        st = path.lstat()
        if path.is_symlink() or st.st_uid != 0 or st.st_mode & 0o777 != mode:
            raise NetworkError('unsafe ownership state permissions')
    signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    if args.operation == 'apply':
        result = apply(args)
    elif args.operation == 'clear':
        clear()
        result = snapshot()
    else:
        state = load_json(STATE)[0] if STATE.exists() else None
        result = snapshot(state)
    json.dump(result, sys.stdout, indent=2, allow_nan=False)
    print()


if __name__ == '__main__':
    try:
        main()
    except (NetworkError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f'network: {error}', file=sys.stderr)
        sys.exit(3)
