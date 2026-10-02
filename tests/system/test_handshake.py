#!/usr/bin/env python3
"""Pure checker mutation fixtures, never network/performance evidence."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tests/system'))
from check_g10 import check_functional_layout, check_history, check_idle, check_warmup_record


def typed_fixture(name):
    """Populate schema types for unit-only consistency checks."""
    definition = json.loads((REPO / 'schemas/result-records.schema.json').read_text())['$defs'][name]
    record = {}
    for key, rule in definition['properties'].items():
        types = rule['type'] if isinstance(rule['type'], list) else [rule['type']]
        if 'const' in rule:
            record[key] = rule['const']
        elif 'null' in types:
            record[key] = None
        elif 'enum' in rule:
            record[key] = rule['enum'][0]
        elif 'boolean' in types:
            record[key] = False
        elif 'number' in types or 'integer' in types:
            record[key] = rule.get('minimum', 0)
        else:
            record[key] = ''
    return record


def rejected_history_fixture():
    run = typed_fixture('run')
    run.update(experiment_id='unit', run_id='unit_rejected', phase='measured', pair_id='unit_pair',
               timestamp_utc='2026-10-01T00:00:00Z', scenario='loopback-test', transport='quic', mode='early',
               trace_mode='performance', network_profile='loopback-test', resource_count=1,
               resource_size_bytes=1024, chunk_bytes=1024, bytes_expected=1024, bytes_received=0,
               tls_resumed=True, attempted_0rtt=True, used_0rtt=False, early_rejected=True,
               early_ready_ms=1, handshake_ms=2, connect_ms=2, elapsed_ms=3,
               error_code='protocol_error', error_message='unit rejection')
    stream = typed_fixture('stream')
    stream.update(experiment_id='unit', run_id=run['run_id'], resource_id=1, transport_stream_id=0,
                  bytes_expected=1024, bytes_received=0, request_start_ms=1, request_end_ms=1.2,
                  error_code='protocol_error', error_message='unit rejection')
    first = dict(run=run, streams=[stream])
    final = copy.deepcopy(first)
    final['run'].update(fallback_count=1, success=True, bytes_received=1024, elapsed_ms=7,
                        total_ms=6.2, transfer_ms=2.2, goodput_mbps=8192/2200,
                        e2e_goodput_mbps=8192/6200, error_code='', error_message='')
    final['streams'][0].update(attempt_index=1, success=True, bytes_received=1024, checksum_ok=True,
                              request_start_ms=4, request_end_ms=4.2, first_byte_ms=5, payload_done_ms=6,
                              complete_ms=6.2, ttfb_request_ms=1, completion_request_ms=2.2,
                              error_code='', error_message='')
    history = dict(schema_version=1, run_id=run['run_id'], ticket_observed=True, target_invoked=True,
                   attempts=[dict(attempt_index=0, record=first), dict(attempt_index=1, record=copy.deepcopy(final))])
    return history, final


class HandshakeChecks(unittest.TestCase):
    def test_idle_retry_numeric_order_requires_last_pair_quiet(self):
        # Unit-only snapshot fixtures; kernel parsing has its own regressions.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            network = root / 'network'
            network.mkdir()
            base = dict(timestamp_utc='2026-10-01T00:00:00+00:00', scenario='unit', netem_seed=1,
                        config_sha256='unit', client_namespace_id='unit-client', server_namespace_id='unit-server')
            (network / 'unit.after.json').write_text(json.dumps(base))
            for index in range(12):
                for side, second in [('before', 2*index+1), ('after', 2*index+2)]:
                    snapshot = dict(base, timestamp_utc=f'2026-10-01T00:00:{second:02d}+00:00', quiet=index == 11)
                    (network / f'unit.idle-{index}-{side}.json').write_text(json.dumps(snapshot))
            def idle(_, after):
                if not json.loads(after.read_text())['quiet']:
                    raise ValueError('unit transient activity')
            support = SimpleNamespace(idle=idle)
            with patch('check_g10.check_kernel'):
                self.assertEqual(check_idle(root, 'unit', support), datetime.fromisoformat('2026-10-01T00:00:24+00:00'))
                final = network / 'unit.idle-11-after.json'
                final.write_text(json.dumps(dict(base, timestamp_utc='2026-10-01T00:00:24+00:00', quiet=False)))
                with self.assertRaises(ValueError):
                    check_idle(root, 'unit', support)
                final.unlink()
                with self.assertRaises(OSError):
                    check_idle(root, 'unit', support)

    def test_replay_history_binding_duplicate_final_and_old_worker_barrier(self):
        history, final = rejected_history_fixture()
        check_history(history, final)
        for mutation in ('identity', 'duplicate', 'final', 'parallel_replay', 'workload', 'overflow'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(history)
                if mutation == 'identity':
                    changed['run_id'] = 'another_run'
                elif mutation == 'duplicate':
                    changed['attempts'][1]['attempt_index'] = 0
                elif mutation == 'final':
                    changed['attempts'][1]['record']['run']['success'] = False
                elif mutation == 'parallel_replay':
                    changed['attempts'][0]['record']['run']['elapsed_ms'] = 4.1
                elif mutation == 'workload':
                    changed['attempts'][0]['record']['run']['chunk_bytes'] = 512
                else:
                    changed['attempts'][0]['record']['streams'][0]['bytes_received'] = 1025
                with self.assertRaises(ValueError):
                    check_history(changed, final)

    def test_exact_functional_target_count_and_rejection_workload(self):
        run = dict(run_id='rejected', resource_count=6, resource_size_bytes=1024, chunk_bytes=1024,
                   transport='quic', network_profile='loopback-test')
        check_functional_layout('rejected', run, dict(attempted=1))
        for changes, count in [({}, 2), ({'resource_count': 1, 'resource_size_bytes': 6144}, 1),
                               ({'chunk_bytes': 512}, 1), ({'run_id': 'early'}, 1)]:
            with self.subTest(changes=changes, count=count):
                with self.assertRaises(ValueError):
                    check_functional_layout('rejected', dict(run, **changes), dict(attempted=count))

    def test_ticket_warmup_identity_cohort_chronology_and_failed_notification(self):
        _, final = rejected_history_fixture()
        target = final['run']
        prior = dict(target, run_id=target['run_id']+'_ticket', phase='warmup', mode='cold',
                     attempted_0rtt=False, tls_resumed=False, used_0rtt=False,
                     timestamp_utc='2026-09-30T23:59:59Z')
        counts = dict(attempted=1, success=1)
        check_warmup_record(prior, target, True, counts)
        for changes, successes in [({'run_id': 'unrelated_ticket'}, 1), ({'chunk_bytes': 512}, 1),
                                   ({'timestamp_utc': target['timestamp_utc']}, 1), ({}, 0)]:
            with self.subTest(changes=changes, successes=successes):
                with self.assertRaises(ValueError):
                    check_warmup_record(dict(prior, **changes), target, True, dict(counts, success=successes))


if __name__ == '__main__':
    unittest.main()
