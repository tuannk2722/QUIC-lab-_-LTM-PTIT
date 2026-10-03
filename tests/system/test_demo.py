#!/usr/bin/env python3
"""P12 negative/provenance/lifecycle tests; temporary fixtures are not measurements."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('demo_support', REPO / 'scripts/demo-support.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def partial(root):
    write(root / 'manifest.json', dict(demo='basic', uid=os.getuid(), trace_mode='evidence', performance_pooling=False,
          build={'inputs': {}}, config_sha256={}, planned_runs=demo.plan('basic'), runs=[], backup=''))
    write(root / 'build.json', {'inputs': {}})
    write(root / 'source-hashes.json', {})


def backup(root):
    write(root / 'raw.json', {'fixture_only': True})
    check = dict(status='PASS', hol='PASS', early_proof='PASS', full_demo_complete=True,
                 counts=dict(n_planned=23, n_invoked=23, n_success=23, n_failed=0),
                 representative=['loss_0_tcp', 'loss_0_quic'], artifact_sha256={'raw.json': demo.digest(root / 'raw.json')})
    write(root / 'g11-check.json', check)
    return check


class DemoTests(unittest.TestCase):
    def test_cli_invalid_arguments_exit_before_privilege_or_network(self):
        cases = [[], ['unknown'], ['basic', '--runs=2'], ['basic', '--out='],
                 ['basic', '--out=relative'], ['loss', '--backup=relative'],
                 ['basic', '--out=/tmp/a', '--out=/tmp/b']]
        for argv in cases:
            with self.subTest(argv=argv):
                result = subprocess.run(['bash', 'scripts/demo.sh', *argv], cwd=REPO,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 2, result.stderr)
        result = subprocess.run(['bash', 'scripts/demo.sh', 'basic'], cwd=REPO,
                                env=dict(os.environ, NETEM_SEED='123'), capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_invocation_cannot_restart_or_overwrite_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            partial(root)
            demo.invocation(root, 'basic_quic', 'pending')
            before = (root / 'manifest.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                demo.invocation(root, 'basic_quic', 'pending')
            self.assertEqual((root / 'manifest.json').read_bytes(), before)
            demo.invocation(root, 'basic_quic', '1')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                demo.invocation(root, 'basic_quic', '0')
            self.assertEqual(demo.read(root / 'manifest.json')['runs'][0]['exit_code'], 1)

    def test_partial_interrupt_still_records_failed_gate_and_full_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            partial(root)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(demo.finish(root, 130, 0), 1)
            result = demo.read(root / 'demo-check.json')
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(result['counts'], dict(n_planned=1, n_invoked=0, n_success=0, n_failed=0, n_missing=1))
            self.assertEqual(result['cleanup']['original_exit'], 130)
            self.assertTrue(result['errors'])
            self.assertEqual(result['cleanup']['host_unchanged'], dict(link=False, address=False, route=False))

    def test_readonly_replay_rejects_forged_pass_even_when_inventory_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            partial(root)
            with redirect_stdout(io.StringIO()):
                demo.finish(root, 130, 0)
            result = demo.read(root / 'demo-check.json')
            result['status'] = 'PASS'
            write(root / 'demo-check.json', result)
            write(root / 'demo.json', {k: v for k, v in result.items() if k not in ('runs', 'artifact_sha256')})
            hashes = {p: demo.digest(p) for p in root.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(ValueError, 'replay differs: status'):
                demo.verify(root)
            self.assertEqual(hashes, {p: demo.digest(p) for p in hashes})

    def test_readonly_replay_accepts_json_roundtripped_causal_witnesses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / 'manifest.json', {'uid': os.getuid()})
            cleanup = dict(original_exit=0, cleanup_exit=0, host_unchanged=dict(link=True, address=True, route=True))
            write(root / 'cleanup.json', cleanup)
            replay = dict(demo='loss', status='PASS', scope='fixture-only', counts={'n_invoked': 2},
                          proof={'hol': 'PASS'}, runs=[{'hol': {'sack_edges': [(100, 200)]}}], errors=[],
                          backup={}, manifest_sha256=demo.digest(root / 'manifest.json'), cleanup=cleanup)
            saved = dict(replay, artifact_sha256=demo.public_artifacts(root))
            write(root / 'demo-check.json', saved)
            write(root / 'demo.json', {k: v for k, v in saved.items() if k not in ('runs', 'artifact_sha256')})
            hashes = {p: demo.digest(p) for p in root.rglob('*') if p.is_file()}
            with patch.object(demo, 'evaluate', return_value=replay):
                self.assertEqual(demo.verify(root)['status'], 'PASS')
            self.assertEqual(hashes, {p: demo.digest(p) for p in hashes})

    def test_backup_checks_all_artifacts_and_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'p11-fixture'
            check = backup(root)
            self.assertEqual(demo.backup_evidence(root)['status'], 'PASS')
            (root / 'raw.json').write_text('changed\n')
            with self.assertRaises((ValueError, FileNotFoundError)):
                demo.backup_evidence(root, Path(temp) / 'absent-review.json')
            check['artifact_sha256'] = {'../escape': '0' * 64}
            write(root / 'g11-check.json', check)
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                demo.backup_evidence(root)

    def test_backup_self_log_exception_is_bound_to_original_receipt_and_completed_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'p11-fixture'
            check = backup(root)
            log = root / 'logs/check.log'
            log.parent.mkdir()
            log.write_text('completed fixture log\n')
            empty = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
            check['artifact_sha256']['logs/check.log'] = empty
            write(root / 'g11-check.json', check)
            prefix = 'results/p11-fixture'
            review_file = Path(temp) / 'review.json'
            review = dict(status='PASS', actual_root=prefix, original_public_hash_audit=dict(
                recorded_count=2, matching=1, exceptions=[dict(path='logs/check.log', recorded_sha256=empty,
                    actual_sha256=demo.digest(log), bytes=log.stat().st_size)]), archive=dict(inventory={
                prefix + '/logs/check.log': {'sha256': demo.digest(log)},
                prefix + '/g11-check.json': {'sha256': demo.digest(root / 'g11-check.json')}}))
            write(review_file, review)
            self.assertEqual(demo.backup_evidence(root, review_file)['status'], 'PASS')
            log.write_text('tampered after review\n')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                demo.backup_evidence(root, review_file)

    def test_artifact_inventory_excludes_secrets_and_still_open_checker_log(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / 'raw.json', {'fixture_only': True})
            (root / 'client.keylog').touch()
            (root / 'logs').mkdir()
            (root / 'logs/check.log').touch()
            hashes = demo.public_artifacts(root)
            self.assertEqual(set(hashes), {'raw.json'})
            (root / 'logs/check.log').write_text('completed after inventory\n')
            self.assertEqual(demo.public_artifacts(root), hashes)
            (root / 'raw.json').write_text('changed\n')
            self.assertNotEqual(demo.public_artifacts(root), hashes)

    def test_production_owner_environment_removes_root_settings_and_preserves_seed(self):
        definition = next(line for line in (REPO / 'scripts/demo.sh').read_text().splitlines()
                          if line.startswith('run_user()'))
        code = '''SUDO_UID=$(id -u); SUDO_GID=$(id -g)
setpriv() {
 local -a arguments=()
 for argument in "$@"; do
  if [[ $argument == --init-groups ]]; then arguments+=(--keep-groups); else arguments+=("$argument"); fi
 done
 command setpriv "${arguments[@]}"
}
''' + definition + '''
run_user python3 -c 'import json,os,shutil;print(json.dumps({k:os.environ.get(k) for k in ["HOME","USER","LOGNAME","XDG_CONFIG_HOME","WIRESHARK_CONFIG_DIR","NETEM_SEED","PATH"]}))'
'''
        env = dict(os.environ, HOME='/root', USER='root', LOGNAME='root', XDG_CONFIG_HOME='/root/.config',
                   WIRESHARK_CONFIG_DIR='/root/wireshark', NETEM_SEED='none')
        result = subprocess.run(['bash', '-euo', 'pipefail', '-c', code], cwd=REPO,
                                env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(result.stdout)
        owner = pwd.getpwuid(os.getuid())
        self.assertEqual((actual['HOME'], actual['USER'], actual['LOGNAME']), (owner.pw_dir, owner.pw_name, owner.pw_name))
        self.assertIsNone(actual['XDG_CONFIG_HOME'])
        self.assertIsNone(actual['WIRESHARK_CONFIG_DIR'])
        self.assertEqual(actual['NETEM_SEED'], 'none')
        self.assertIn('/usr/sbin', actual['PATH'].split(':'))

    def run_fixture(self, root, transport, mode='cold', profile='handshake', scenario='baseline'):
        entry = dict(run_id='fixture', transport=transport, mode=mode, profile=profile, scenario=scenario,
                     exit_code=0, out='runs/fixture', client_qlog='client-qlog', server_qlog='server-qlog',
                     client_keylog='client.keylog', server_keylog='server.keylog', captures='captures/fixture')
        run = dict(phase='evidence', trace_mode='evidence', run_id='fixture', mode=mode, transport=transport,
                   success=True, resource_count=1 if profile == 'handshake' else 6,
                   resource_size_bytes=1024 if profile == 'handshake' else 1048576,
                   chunk_bytes=1024 if profile == 'handshake' else 16384, bytes_received=1024, total_ms=100,
                   used_0rtt=mode == 'early', tls_resumed=mode != 'cold', attempted_0rtt=mode == 'early',
                   early_rejected=False, fallback_count=0, timestamp_utc='1970-01-01T00:00:00Z')
        for name in ('client.keylog', 'server.keylog'):
            (root / name).touch(mode=0o600)
        return entry, {'run': run, 'streams': [{'resource_id': 1, 'transport_stream_id': 0}]}

    def test_successful_quic_requires_correlated_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry, record = self.run_fixture(root, 'quic')
            with patch.object(demo, 'check_progress', return_value=(record, [])), \
                 patch.object(demo, 'network', return_value={}), patch.object(demo, 'correlated', return_value=[]):
                with self.assertRaisesRegex(ValueError, 'qlog connection count'):
                    demo.audit_run(root, entry, os.getuid())

    def test_early_api_and_ranges_without_decrypted_request_remain_inconclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry, record = self.run_fixture(root, 'quic', 'early')
            target = dict(role='target', client_endpoint={'ip_v4': '10.10.0.1', 'port_v4': 12345},
                          server_endpoint={'ip_v4': '10.10.0.2', 'port_v4': 4433})
            initial = dict(protocol='udp', quic=True, packet_type=0, packet_number=0, streams=[], epoch=1)
            # Looks like a 0RTT STREAM, but the content is not a QB01 REQUEST.
            early = dict(protocol='udp', quic=True, packet_type=1, packet_number=1, epoch=2,
                         src='10.10.0.1', srcport=12345, dst='10.10.0.2', dstport=4433,
                         streams=[dict(stream_id=0, offset=0, length=32, data_hex='00' * 32)])
            with patch.object(demo, 'check_progress', return_value=(record, [])), \
                 patch.object(demo, 'network', return_value={}), \
                 patch.object(demo, 'correlated', return_value=[target, {'role': 'ticket'}]), \
                 patch.object(demo, 'viewer'), patch.object(demo, 'render_timeline'), \
                 patch.object(demo, 'audit_capture', return_value=root), \
                 patch.object(demo, 'decode', side_effect=lambda *args: copy.deepcopy([initial, early])), \
                 patch.object(demo, 'early_qlog', return_value={'status': 'PASS', 'matched': [{'packet_number': 1, 'stream_id': 0}]}):
                result = demo.audit_run(root, entry, os.getuid())
            self.assertEqual(result['early_proof'], 'INCONCLUSIVE')
            self.assertTrue(all(p['status'] == 'INCONCLUSIVE' for p in result['early_packet'].values()))

    def test_paired_tcp_capture_identity_reaches_causal_hol_checker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry, record = self.run_fixture(root, 'tcp', profile='bulk', scenario='rtt50-loss3')
            points = [dict(elapsed_ms=1900, resource_id=1, payload_bytes_received=16384),
                      dict(elapsed_ms=2200, resource_id=1, payload_bytes_received=32768)]
            def packet(epoch, number, source, seq, ack, length, sacks=()):
                return dict(protocol='tcp', epoch=epoch, frame_number=number, srcport=4433 if source == 'qserver' else 12345,
                            dstport=12345 if source == 'qserver' else 4433, seq=seq, ack=ack, length=length,
                            sack_left=[e[0] for e in sacks], sack_right=[e[1] for e in sacks])
            client = [packet(2, 10, 'qclient', 0, 100, 0, [(200, 300)]), packet(2.1, 20, 'qclient', 0, 300, 0)]
            server = [packet(1.9, 1, 'qserver', 100, 0, 100), packet(1.99, 2, 'qserver', 200, 0, 100),
                      packet(2.04, 3, 'qserver', 100, 0, 100)]
            with patch.object(demo, 'check_progress', return_value=(record, points)), \
                 patch.object(demo, 'network', return_value={}), patch.object(demo, 'viewer'), \
                 patch.object(demo, 'render_timeline'), \
                 patch.object(demo, 'audit_capture', side_effect=lambda out, entry, ns, uid: root / ns), \
                 patch.object(demo, 'decode', side_effect=lambda pcap, *args: copy.deepcopy(client if 'qclient' in pcap.parts else server)):
                result = demo.audit_run(root, entry, os.getuid())
            self.assertEqual(result['hol']['status'], 'PASS')
            self.assertEqual(result['hol']['retry_frame'], 3)


if __name__ == '__main__':
    unittest.main()
