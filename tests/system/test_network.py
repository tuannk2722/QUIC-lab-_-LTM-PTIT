#!/usr/bin/env python3
"""Unprivileged negative-path tests. These are not G08 traffic evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('network_state', ROOT / 'scripts/network/state.py')
network = importlib.util.module_from_spec(spec)
spec.loader.exec_module(network)
checker_spec = importlib.util.spec_from_file_location('check_g08', ROOT / 'tests/system/check_g08.py')
checker = importlib.util.module_from_spec(checker_spec)
checker_spec.loader.exec_module(checker)


class NetworkTests(unittest.TestCase):
    def state(self, profile='ingress-ifb'):
        cfg, item, digest = network.scenario_config(ROOT / 'configs/scenarios.json', 'rtt50-loss3')
        return dict(item, network_profile=profile, netem_seed=cfg['base_seed'],
                    queue_limit_packets=cfg['queue_limit_packets'])

    def q(self, loss=.03):
        return {'kind': 'netem', 'handle': '1:', 'root': True,
                'options': {'limit': 1000, 'delay': {'delay': .025, 'jitter': 0},
                            'loss-random': {'loss': loss}, 'rate': {'rate': 2500000}, 'seed': 20260928}}

    def test_actual_units_loss_direction_and_seed(self):
        for profile in ('ingress-ifb', 'egress-demo'):
            state = self.state(profile)
            for ns in network.NAMES:
                downstream = (ns == 'qclient') == (profile == 'ingress-ifb')
                q = self.q(.03 if downstream else 0)
                network.verify_netem(q, state, ns)
                for field, value in [('delay', {'delay': .050}), ('rate', {'rate': 20000000}),
                                     ('seed', 1), ('limit', 50), ('duplicate', {'duplicate': .01})]:
                    bad = copy.deepcopy(q)
                    bad['options'][field] = value
                    with self.assertRaises(network.NetworkError):
                        network.verify_netem(bad, state, ns)
        with self.assertRaises(network.NetworkError):
            network.verify_netem(self.q(0), self.state(), 'qclient')

    def test_scenario_strict_bounds_and_duplicate_input(self):
        good = (ROOT / 'configs/scenarios.json').read_text()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'cfg.json'
            for data in [good.replace('"rate_mbps": 20', '"rate_mbps": 0'),
                         good.replace('"loss_downstream_pct": 0', '"loss_downstream_pct": true'),
                         good.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'),
                         good.replace('rtt50-loss0', 'baseline'),
                         good + '{}', 'null', ' ' * ((1 << 20) + 1)]:
                path.write_text(data)
                with self.assertRaises(ValueError):
                    network.scenario_config(path, 'baseline')

    def test_foreign_qdisc_refused_before_delete(self):
        with patch.object(network, 'qdiscs', return_value=[{'kind': 'fq_codel', 'handle': '5:', 'root': True}]), patch.object(network, 'tc') as tc:
            with self.assertRaises(network.NetworkError):
                network.clear()
            tc.assert_not_called()

    def test_kernel_ifb_default_survives_clear_and_checker(self):
        defaults = {'eth0': {'kind': 'noqueue', 'handle': '0:', 'root': True},
                    'ifb0': {'kind': 'fq_codel', 'handle': '0:', 'root': True}}
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / 'state.json'
            state.write_text('{}')
            with patch.object(network, 'STATE', state), patch.object(network, 'qdiscs',
                    side_effect=lambda ns, dev: [defaults[dev]]), patch.object(network, 'tc') as tc:
                network.clear()
                network.clear()
                tc.assert_not_called()
                self.assertFalse(state.exists())
            snapshot = {'verified': False, 'observation': {ns: dict(filters=[],
                **{dev: {'qdisc': [q]} for dev, q in defaults.items()}) for ns in network.NAMES}}
            path = Path(temp) / 'clear.json'
            path.write_text(json.dumps(snapshot))
            self.assertEqual(checker.cleared(path)['status'], 'PASS')
            for bad in [dict(defaults['ifb0'], handle='5:'),
                        dict(defaults['ifb0'], root=False),
                        dict(defaults['ifb0'], kind='netem')]:
                self.assertFalse(network.default_qdisc(bad, 'ifb0'))
                snapshot['observation']['qclient']['ifb0']['qdisc'] = [bad]
                path.write_text(json.dumps(snapshot))
                with self.assertRaises(ValueError):
                    checker.cleared(path)
            self.assertFalse(network.default_qdisc(defaults['ifb0'], 'eth0'))

    def test_tc_failure_rolls_back_partial_apply_and_keeps_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            state_path = Path(temp) / 'state.json'
            args = types.SimpleNamespace(scenarios=str(ROOT / 'configs/scenarios.json'), scenario='rtt50-loss3', profile='ingress-ifb', seed='default')
            error = network.NetworkError('actual tc failed')
            calls = []
            def tc(ns, *argv):
                calls.append((ns, argv))
                if ns == 'qserver':
                    raise error
            with patch.object(network, 'STATE', state_path), patch.object(network, 'identity', side_effect=lambda ns: ns), patch.object(network, 'clear') as clear, patch.object(network, 'prepare_offloads', return_value={}), patch.object(network, 'tc', side_effect=tc):
                with self.assertRaisesRegex(network.NetworkError, 'actual tc failed'):
                    network.apply(args)
                self.assertEqual(clear.call_count, 2)
                self.assertTrue(any(ns == 'qclient' for ns, _ in calls))
                self.assertFalse(state_path.exists())

    def test_offload_fixed_on_cannot_claim_verified(self):
        network.check_offloads('generic-receive-offload: off [fixed]\n', 'test')
        for feature in network.FEATURES:
            with self.assertRaises(network.NetworkError):
                network.check_offloads(f'{feature}: on [fixed]\n', 'test')

    def test_filter_requires_lab_direction_and_redirect(self):
        f = {'kind': 'flower', 'protocol': 'ip', 'pref': 10, 'options': {
            'keys': {'src_ip': '10.10.0.2', 'dst_ip': '10.10.0.1'},
            'actions': [{'kind': 'mirred', 'to_dev': 'ifb0', 'mirred_action': 'redirect', 'direction': 'egress'}]}}
        network.check_filters([f], 'qclient')
        for target, value in [('to_dev', 'eth0'), ('mirred_action', 'mirror'), ('direction', 'ingress')]:
            bad = copy.deepcopy(f)
            bad['options']['actions'][0][target] = value
            with self.assertRaises(network.NetworkError):
                network.check_filters([bad], 'qclient')
        with self.assertRaises(network.NetworkError):
            network.check_filters([f], 'qserver')
        with self.assertRaises(network.NetworkError):
            network.check_filters([f, f], 'qclient')
        bad = copy.deepcopy(f)
        bad['options']['keys']['ip_proto'] = 'tcp'
        with self.assertRaises(network.NetworkError):
            network.check_filters([bad], 'qclient')

    def test_rtt_gate_rejects_short_lossy_and_double_delay(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'synthetic-unit-probe.log'
            for count, rtt, loss in [(9, 50, 0), (12, 50, 10), (12, 100, 0)]:
                path.write_text(f'{loss}% packet loss\n'+f'time={rtt} ms\n'*count)
                with self.assertRaises(ValueError):
                    checker.probe(path, 'rtt50-loss0', 'qclient')

    def test_signal_during_apply_rolls_back_without_publishing(self):
        args = types.SimpleNamespace(scenarios=str(ROOT/'configs/scenarios.json'), scenario='baseline', profile='ingress-ifb', seed='default')
        with patch.object(network, 'identity', side_effect=lambda ns: ns), patch.object(network, 'clear') as clear, patch.object(network, 'prepare_offloads', side_effect=SystemExit(130)), patch.object(network, 'save_state') as save:
            with self.assertRaises(SystemExit) as caught:
                network.apply(args)
            self.assertEqual(caught.exception.code, 130)
            self.assertEqual(clear.call_count, 2)
            save.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
