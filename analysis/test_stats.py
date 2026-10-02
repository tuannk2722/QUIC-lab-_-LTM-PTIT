"""Contract statistics tests; synthetic numbers are unit fixtures only."""
import math
import copy
import json
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from cohort import HANDSHAKE_MODES, handshake_schedule, handshake_sidecars, handshake_state
from summarize import COLUMNS, GROUP, HANDSHAKE_COLUMNS, stats, summarize_rows


class StatisticsTests(unittest.TestCase):
    def test_nearest_rank_even_median_and_sample_stddev(self):
        s = stats([1, 2, 3, 4])
        self.assertEqual(s['median'], 2.5)
        self.assertEqual(s['p95'], 4)
        self.assertAlmostEqual(s['sample_stddev'], math.sqrt(5/3))
        self.assertEqual(stats(list(range(1, 31)))['p95'], 29)
        self.assertIsNone(stats([3])['sample_stddev'])
        self.assertIsNone(stats([])['mean'])

    def test_failures_warmups_and_outliers(self):
        def row(value, success=True, phase='measured'):
            r = dict(zip(GROUP, ['baseline', 'tcp', 'cold', 'ingress-ifb', 'performance', 6, 1048576, 16384]))
            r.update(total_ms=value, success=success, phase=phase, error_code='' if success else 'timeout')
            return r
        values = [row(1), row(3), row(101), row(None, False), row(100000, phase='warmup')]
        result = summarize_rows(values, metrics=['total_ms'])[0]
        self.assertEqual((result['n_attempted'], result['n_success'], result['n_failed']), (4, 3, 1))
        self.assertEqual(result['failure_rate'], .25)
        self.assertEqual(result['n_timeout'], 1)
        self.assertEqual(result['mean'], 35)
        self.assertEqual(result['p95'], 101)
        all_fail = summarize_rows([row(None, False)], metrics=['total_ms'])[0]
        self.assertEqual(all_fail['failure_rate'], 1)
        self.assertIsNone(all_fail['median'])


class HandshakeTests(unittest.TestCase):
    """Synthetic fixtures exercise policies only; they are never result evidence."""

    def target(self, mode='early', success=True, fallback=0, value=10):
        run = dict(zip(GROUP, ['rtt50-loss0', 'quic', mode, 'ingress-ifb', 'performance', 1, 1024, 1024]))
        run.update(run_id='target', experiment_id='test', timestamp_utc='2026-10-01T00:00:00Z',
                   phase='measured', total_ms=value, success=success, error_code='' if success else 'timeout',
                   tls_resumed=mode != 'cold', attempted_0rtt=mode == 'early',
                   used_0rtt=mode == 'early' and not fallback, early_rejected=bool(fallback),
                   fallback_count=fallback, handshake_ms=5, early_ready_ms=1 if mode == 'early' else None)
        stream = {'attempt_index': fallback, 'request_start_ms': 2 if mode == 'early' and not fallback else 6,
                  'request_end_ms': 3 if mode == 'early' and not fallback else 7}
        return run, [stream]

    def test_actual_mode_and_enqueue_qualification(self):
        for mode in HANDSHAKE_MODES:
            with self.subTest(mode=mode):
                run, streams = self.target(mode)
                self.assertTrue(handshake_state(run, streams)['mode_achieved'])
        run, streams = self.target()
        # An early Write START alone is insufficient: its successful return
        # (API enqueue) must precede the observed handshake milestone.
        streams[0]['request_end_ms'] = run['handshake_ms']
        self.assertFalse(handshake_state(run, streams)['latency_eligible'])
        run, streams = self.target('resumed')
        run['tls_resumed'] = False
        self.assertEqual(handshake_state(run, streams)['mode_classification'], 'mode_unachieved')
        run, streams = self.target('resumed')
        streams[0]['request_start_ms'] = 4
        self.assertFalse(handshake_state(run, streams)['mode_achieved'])

    def test_transfer_success_fallback_and_failures_remain_separate(self):
        rows = []
        for success, fallback, value in [(True, 0, 10), (True, 1, 999), (False, 0, None)]:
            run, streams = self.target(success=success, fallback=fallback, value=value)
            run.update(handshake_state(run, streams))
            rows.append(run)
        warm, streams = self.target(value=100000)
        warm['phase'] = 'warmup'
        warm.update(handshake_state(warm, streams))
        rows.append(warm)
        summary = summarize_rows(rows, metrics=['total_ms'], handshake=True)[0]
        self.assertEqual((summary['n_attempted'], summary['n_success'], summary['n_failed']), (3, 2, 1))
        self.assertEqual((summary['n_mode_achieved'], summary['n_fallback'], summary['n_unachieved']), (1, 1, 1))
        self.assertEqual(summary['failure_rate'], 1/3)
        self.assertEqual((summary['n_values'], summary['median'], summary['p95']), (1, 10, 10))
        self.assertIsNone(summarize_rows([rows[1]], metrics=['total_ms'], handshake=True)[0]['median'])
        self.assertEqual(HANDSHAKE_COLUMNS[:len(COLUMNS)], COLUMNS)
        self.assertNotIn('n_fallback', summarize_rows([rows[0]], metrics=['total_ms'])[0])

    def test_contradictory_states_and_duplicate_replay_are_rejected(self):
        for mutation in ['fallback_count', 'early_rejected', 'tls_resumed', 'attempt_index']:
            with self.subTest(mutation=mutation):
                run, streams = self.target(fallback=1)
                if mutation == 'fallback_count':
                    run[mutation] = 2
                elif mutation == 'early_rejected':
                    run[mutation] = False
                elif mutation == 'tls_resumed':
                    run['used_0rtt'] = True
                    run[mutation] = False
                else:
                    streams[0][mutation] = 0
                with self.assertRaises(ValueError):
                    handshake_state(run, streams)

    def test_attempt_history_preserves_original_t0_and_single_replay(self):
        run, streams = self.target(success=False, fallback=1, value=None)
        original, original_streams = self.target(success=False, fallback=0, value=None)
        original.update(early_rejected=True, used_0rtt=False)
        attempts = [{'attempt_index': 0, 'record': {'run': original, 'streams': original_streams}},
                    {'attempt_index': 1, 'record': {'run': run, 'streams': streams}}]
        for mutation in ['none', 'reset_t0', 'third_attempt', 'not_rejected', 'stream_index']:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                current = copy.deepcopy(attempts)
                if mutation == 'reset_t0':
                    current[1]['record']['run']['timestamp_utc'] = '2026-10-01T00:00:01Z'
                elif mutation == 'third_attempt':
                    current.append(copy.deepcopy(current[1]))
                elif mutation == 'not_rejected':
                    current[0]['record']['run']['early_rejected'] = False
                elif mutation == 'stream_index':
                    current[1]['record']['streams'][0]['attempt_index'] = 0
                path = directory / 'shards' / run['run_id'] / 'attempts'
                path.mkdir(parents=True)
                (path / 'target.json').write_text(json.dumps({'schema_version': 1, 'run_id': 'target',
                    'target_invoked': True, 'ticket_observed': True, 'attempts': current}))
                if mutation == 'none':
                    handshake_sidecars(directory, run, streams)
                else:
                    with self.assertRaises(ValueError):
                        handshake_sidecars(directory, run, streams)

    def schedule(self):
        plan = {'profile': 'handshake', 'scenario_names': ['rtt50-loss0'], 'runs': 30, 'warmups': 2,
                'execution': 'ingress-ifb', 'workloads': {'profiles': {'handshake': {
                'resource_count': 1, 'resource_size_bytes': 1024, 'chunk_bytes': 1024}}},
                'scenarios': {'scenarios': [{'name': 'rtt50-loss0', 'delay_each_way_ms': 25,
                'loss_downstream_pct': 0, 'loss_upstream_pct': 0, 'rate_mbps': 20}]}}
        orders = [('cold', 'resumed', 'early'), ('resumed', 'early', 'cold'), ('early', 'cold', 'resumed'),
                  ('early', 'resumed', 'cold'), ('resumed', 'cold', 'early'), ('cold', 'early', 'resumed')]
        groups = defaultdict(list)
        seed = 0
        for phase, count in [('warmup', 2), ('measured', 30)]:
            for repeat in range(count):
                seed += 1
                for pos, mode in enumerate(orders[repeat % 6]):
                    groups[phase, repeat].append({'phase': phase, 'repeat_index': repeat, 'scenario': 'rtt50-loss0',
                        'mode': mode, 'transport': 'quic', 'order_index': pos, 'netem_seed': seed})
        return plan, groups

    def test_full_triple_counts_permutations_and_seed_binding(self):
        for mutation in ['none', 'duplicate_mode', 'seed_reuse', 'triple_seed', 'missing_triple', 'loopback_main']:
            with self.subTest(mutation=mutation):
                plan, groups = self.schedule()
                if mutation == 'duplicate_mode':
                    groups['measured', 0][1]['mode'] = 'cold'
                elif mutation == 'seed_reuse':
                    for row in groups['measured', 1]:
                        row['netem_seed'] = groups['measured', 0][0]['netem_seed']
                elif mutation == 'triple_seed':
                    groups['measured', 0][1]['netem_seed'] = 999
                elif mutation == 'missing_triple':
                    del groups['measured', 29]
                elif mutation == 'loopback_main':
                    plan['execution'] = 'loopback-test'
                if mutation == 'none':
                    handshake_schedule(plan, groups, strict=True)
                else:
                    with self.assertRaises(ValueError):
                        handshake_schedule(plan, groups, strict=True)

    def test_plot_groups_never_pool_quic_modes(self):
        from plot import plot_groups
        rows = [self.target(mode)[0] for mode in HANDSHAKE_MODES]
        groups = plot_groups(rows, handshake=True)
        self.assertEqual([g[2] for g in groups], list(HANDSHAKE_MODES))
        self.assertEqual([len(g[3]) for g in groups], [1, 1, 1])


if __name__ == '__main__':
    unittest.main()
