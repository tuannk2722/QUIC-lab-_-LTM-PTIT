#!/usr/bin/env python3
"""G12 acceptance mutations in disposable synthetic fixtures; no network proof."""
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('g12_acceptance', REPO / 'tests/system/check_g12.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
spec = importlib.util.spec_from_file_location('g12_reproduction', REPO / 'tests/system/run_g12_software.py')
reproduction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reproduction)
spec = importlib.util.spec_from_file_location('g12_rehearsal', REPO / 'scripts/g12-rehearse.py')
rehearsal_driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rehearsal_driver)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def fixture_commit(path):
    """Only disposable synthetic /tmp repositories, never the user's checkout."""
    subprocess.run(['git', 'init', '-q', str(path)], check=True)
    subprocess.run(['git', '-C', str(path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(path), '-c', 'user.name=G12 synthetic fixture',
                    '-c', 'user.email=g12-fixture@example.invalid', '-c', 'commit.gpgsign=false',
                    'commit', '-qm', 'Synthetic unit fixture'], check=True)
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()


class G12AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='g12-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / 'source'
        self.root = self.base / 'gate'
        self.fresh = self.root / 'fresh'
        self.source.mkdir()
        self.fresh.mkdir(parents=True)
        for name in ('Makefile', 'go.mod', 'go.sum', 'scripts/demo.sh', 'scripts/demo-support.py'):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic fixture: ' + name + '\n')
        for name in ('README.md', 'docs/DEMO_SCRIPT.md', 'docs/REPORT.md',
                     'docs/AI_USAGE.md', 'docs/THEORY_AND_DEFENSE.md', 'docs/evidence/p12/README.md'):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic packaging fixture. No measured results.\n')
        self.ledger = self.source / 'docs/ACCEPTANCE_RESULTS.md'
        evidence = self.source / 'docs/evidence/gate-fixture.log'
        evidence.write_text('Synthetic fixture, not evidence of a real acceptance run.\n')
        self.ledger.write_text('\n'.join(
            '| ' + f'G{i:02}' + (' overall' if i >= 7 else '-case') +
            ' | PASS | fixture | [fixture](evidence/gate-fixture.log) |'
            for i in range(12)) + '\n')
        original = self.source / 'docs/references/originals/synthetic.txt'
        original.parent.mkdir(parents=True)
        original.write_text('Synthetic historical-input fixture.\n')
        put(self.source / 'docs/references/SOURCE_MANIFEST.json', dict(files=[dict(
            file='synthetic.txt', bytes=original.stat().st_size, sha256=gate.digest(original))]))
        archive = self.source / 'docs/evidence/p11/synthetic-bundle.tar.gz'
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b'Synthetic checksum fixture; not a real archive or measured run.\n')
        self.review = dict(status='PASS', user_gate_exit=0,
                           checker_original=dict(status='PASS', counts=dict(
                               n_planned=23, n_invoked=23, n_success=23, n_failed=0),
                               early_proof='PASS', hol='PASS', full_demo_complete=True),
                           cleanup=dict(original_exit=0, cleanup_exit=0),
                           host_byte_identical=dict(link=True, address=True, route=True),
                           archive=dict(byte_verified=True,
                                        path=str(archive.relative_to(self.source)), sha256=gate.digest(archive)))
        put(self.source / 'docs/evidence/p11/g11-rerun-review.json', self.review)
        for path in self.source.rglob('*'):
            if path.is_file():
                target = self.fresh / path.relative_to(self.source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        source_hashes = {str(p.relative_to(self.source)): gate.digest(p)
                         for p in self.source.rglob('*') if p.is_file()}
        base_commit = fixture_commit(self.fresh)
        self.steps = []
        for name in ('modules', 'build', 'certs', 'doctor', 'go-tests', 'analysis-tests',
                     'network-tests', 'demo-tests', 'g12-tests', 'localhost', 'localhost-check', 'analyze', 'public-targets'):
            log = self.root / 'logs' / (name + '.log')
            log.parent.mkdir(exist_ok=True)
            log.write_text('Synthetic unit-test command log.\n')
            self.steps.append(dict(name=name, exit=0, log=str(log.relative_to(self.root)), sha256=gate.digest(log)))
        self.cohort = self.fresh / 'results/analysis-fixture'
        self.cohort.mkdir(parents=True)
        (self.cohort / 'runs.csv').write_text('synthetic,unit,fixture\n')
        self.software = dict(status='PASS', uid=max(1, os.getuid()), empty_build_cache=True,
                             starting_artifacts={'bin': [], 'certs': ['.gitkeep'], 'results': ['.gitkeep']},
                             source_root=str(self.source), fresh_root=str(self.fresh), source_hashes=source_hashes,
                             checkout=dict(base_commit=base_commit, local_origin=str(self.source),
                                           candidate_overlay=True, new_commit=False),
                             steps=self.steps, analysis_root=str(self.cohort),
                             analysis_raw_hashes={'runs.csv': gate.digest(self.cohort / 'runs.csv')})
        self.save_software()

    def save_software(self):
        put(self.root / 'software.json', self.software)

    def refresh_export_hash(self, name):
        self.software['source_hashes'][name] = gate.digest(self.fresh / name)
        self.save_software()

    def full_fixture(self):
        steps = []
        for number, (name, target) in enumerate((('baseline', 'demo-baseline'), ('basic', 'demo-quic-basic'),
                                                ('loss', 'demo-loss'), ('0rtt', 'demo-0rtt'), ('cleanup', 'cleanup'))):
            phase = 'preparation' if name == 'baseline' else 'rehearsal'
            log = self.root / 'logs' / (phase + '-' + name + '.log')
            log.write_text('Synthetic terminal rehearsal unit fixture.\n')
            argv = ['make', target]
            if name != 'cleanup':
                argv.extend(['DEMO_OUT=' + str(self.root / 'demos' / name), 'DEMO_BACKUP=' + str(self.base / 'backup')])
                put(self.root / 'demos' / name / 'demo-check.json', dict(status='PASS'))
                put(self.root / 'demos' / name / 'cleanup.json', dict(original_exit=0, cleanup_exit=0))
                check_log = self.root / 'demos' / name / 'logs/check.log'
                check_log.parent.mkdir()
                check_log.write_text('Synthetic completed demo audit log.\n')
            steps.append(dict(name=name, argv=argv, exit=0, start_seconds=number * 60,
                              end_seconds=number * 60 + 10, log=str(log.relative_to(self.root)), sha256=gate.digest(log)))
        preparation = dict(status='PASS', uid=self.software['uid'], offline=True, elapsed_seconds=10,
                           scope='baseline Make acceptance before live A→C→B clock', steps=steps[:1],
                           started_utc='2026-10-02T00:00:00+00:00', finished_utc='2026-10-02T00:00:10+00:00')
        put(self.root / 'preparation.json', preparation)
        rehearsal = dict(schema_version=2, status='PASS', uid=self.software['uid'], offline=True, elapsed_seconds=360,
                         started_utc='2026-10-02T00:00:10+00:00', finished_utc='2026-10-02T00:06:10+00:00',
                         preparation=dict(path='preparation.json', sha256=gate.digest(self.root / 'preparation.json')),
                         presentation_policy='timed terminal walkthrough; human oral delivery not certified', steps=steps[1:])
        put(self.root / 'rehearsal.json', rehearsal)
        return rehearsal

    def check_full_fixture(self):
        # Isolate the orchestration contract here. test_demo.py exercises the
        # real delegated verifier; these unit fixtures contain no PCAP/qlog.
        loader = SimpleNamespace(exec_module=lambda _module: None)
        verifier = SimpleNamespace(verify=mock.Mock())
        with mock.patch('importlib.util.spec_from_file_location', return_value=SimpleNamespace(loader=loader)), \
                mock.patch('importlib.util.module_from_spec', return_value=verifier):
            return gate.check(self.root)

    def test_complete_software_package(self):
        self.assertEqual(gate.check(self.root, software_only=True)['status'], 'PASS')

    def test_source_pins_current_and_exported_changes(self):
        for name in ('go.mod', 'go.sum', 'scripts/demo.sh'):
            with self.subTest(name=name):
                path = self.source / name
                old = path.read_text()
                path.write_text(old + 'changed\n')
                with self.assertRaisesRegex(ValueError, 'current implementation changed'):
                    gate.check_source(self.software, self.fresh)
                path.write_text(old)
        (self.fresh / 'scripts/demo.sh').write_text('changed exported code\n')
        with self.assertRaisesRegex(ValueError, 'exported source changed'):
            gate.check_source(self.software, self.fresh)

    def test_new_unexported_source_is_stale(self):
        (self.source / 'scripts/new-entry.py').write_text('pass\n')
        with self.assertRaisesRegex(ValueError, 'current implementation changed'):
            gate.check_source(self.software, self.fresh)

    def test_runtime_task_update_does_not_stale_implementation(self):
        (self.source / '.codex').mkdir()
        (self.source / '.codex/TASK.md').write_text('unit fixture runtime checkpoint\n')
        gate.check_source(self.software, self.fresh)

    def test_failed_overall_cannot_use_software_pass(self):
        ledger = self.fresh / 'docs/ACCEPTANCE_RESULTS.md'
        ledger.write_text(ledger.read_text().replace('| G11 overall | PASS', '| G11 overall | FAIL') +
                          '| G11-software | PASS | [fixture](evidence/gate-fixture.log) |\n')
        with self.assertRaisesRegex(ValueError, 'G11 overall not PASS'):
            gate.check_prior_gates(self.fresh)

    def test_missing_overall_cannot_use_software_pass(self):
        ledger = self.fresh / 'docs/ACCEPTANCE_RESULTS.md'
        ledger.write_text(ledger.read_text().replace('G08 overall', 'G08-software'))
        with self.assertRaisesRegex(ValueError, 'G08 overall not PASS'):
            gate.check_prior_gates(self.fresh)

    def test_actual_g11_denominator_and_archive_bound(self):
        self.review['checker_original']['counts']['n_invoked'] = 22
        put(self.fresh / 'docs/evidence/p11/g11-rerun-review.json', self.review)
        with self.assertRaisesRegex(ValueError, 'G11 incomplete denominator'):
            gate.check_prior_gates(self.fresh)
        self.review['checker_original']['counts']['n_invoked'] = 23
        put(self.fresh / 'docs/evidence/p11/g11-rerun-review.json', self.review)
        (self.fresh / self.review['archive']['path']).write_bytes(b'changed bundle')
        with self.assertRaisesRegex(ValueError, 'G11 public archive differs'):
            gate.check_prior_gates(self.fresh)

    def test_missing_software_step_rejected(self):
        self.software['steps'] = [step for step in self.steps if step['name'] != 'localhost-check']
        self.save_software()
        with self.assertRaisesRegex(ValueError, 'missing reproduction steps'):
            gate.check(self.root, software_only=True)

    def test_changed_command_log_rejected(self):
        (self.root / self.steps[0]['log']).write_text('changed log\n')
        with self.assertRaisesRegex(ValueError, 'failed or changed reproduction log'):
            gate.check(self.root, software_only=True)

    def test_analysis_cannot_change_canonical_data(self):
        (self.cohort / 'runs.csv').write_text('changed canonical fixture\n')
        with self.assertRaisesRegex(ValueError, 'analysis modified source data'):
            gate.check(self.root, software_only=True)

    def test_originals_are_independently_bound(self):
        name = 'docs/references/originals/synthetic.txt'
        (self.fresh / name).write_text('changed historical original\n')
        self.refresh_export_hash(name)
        with self.assertRaisesRegex(ValueError, 'historical original changed'):
            gate.check(self.root, software_only=True)

    def test_complete_terminal_walkthrough(self):
        self.full_fixture()
        self.assertEqual(self.check_full_fixture()['status'], 'PASS')

    def test_rehearsal_mandatory_order_command_and_logs(self):
        rehearsal = self.full_fixture()
        baseline = json.loads(json.dumps(rehearsal))
        mutations = (
            ('missing', lambda value: value['steps'].pop()),
            ('wrong order', lambda value: value['steps'].reverse()),
            ('wrong command', lambda value: value['steps'][0]['argv'].__setitem__(1, 'doctor')),
            ('wrong output', lambda value: value['steps'][0]['argv'].__setitem__(2, 'DEMO_OUT=/different/output')),
            ('failed command', lambda value: value['steps'][0].__setitem__('exit', 1)),
            ('changed log hash', lambda value: value['steps'][0].__setitem__('sha256', '0' * 64)),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                value = json.loads(json.dumps(baseline))
                mutate(value)
                put(self.root / 'rehearsal.json', value)
                with self.assertRaises(ValueError):
                    self.check_full_fixture()

    def test_rehearsal_duration_not_just_pass_label(self):
        rehearsal = self.full_fixture()
        for elapsed in (299, 423.01996559):
            with self.subTest(elapsed=elapsed):
                rehearsal['elapsed_seconds'] = elapsed
                put(self.root / 'rehearsal.json', rehearsal)
                with self.assertRaisesRegex(ValueError, '5–7 minutes'):
                    self.check_full_fixture()

    def test_baseline_preparation_required_and_hash_bound(self):
        rehearsal = self.full_fixture()
        receipt = self.root / 'preparation.json'
        original = json.loads(receipt.read_text())
        for mutation in ('failed', 'missing target', 'wrong target', 'after live', 'overlap', 'offline', 'owner', 'log'):
            with self.subTest(mutation=mutation):
                value = json.loads(json.dumps(original))
                if mutation == 'failed': value['status'] = 'FAIL'
                elif mutation == 'missing target': value['steps'] = []
                elif mutation == 'wrong target': value['steps'][0]['argv'][1] = 'doctor'
                elif mutation == 'after live': value['finished_utc'] = rehearsal['finished_utc']
                elif mutation == 'overlap': value['steps'][0]['end_seconds'] = 11
                elif mutation == 'offline': value['offline'] = False
                elif mutation == 'owner': value['uid'] += 1
                elif mutation == 'log': value['steps'][0]['sha256'] = '0' * 64
                put(receipt, value)
                rehearsal['preparation']['sha256'] = gate.digest(receipt)
                put(self.root / 'rehearsal.json', rehearsal)
                with self.assertRaises(ValueError): self.check_full_fixture()
        put(receipt, original)
        with self.assertRaisesRegex(ValueError, 'preparation receipt changed'):
            self.check_full_fixture()
        receipt.unlink()
        with self.assertRaises(OSError): self.check_full_fixture()

    def test_live_clock_rejects_overlapping_or_unbounded_commands(self):
        rehearsal = self.full_fixture()
        for start, end in ((-1, 5), (1, 361), (100, 99), (float('nan'), 10)):
            with self.subTest(start=start, end=end):
                rehearsal['steps'][0].update(start_seconds=start, end_seconds=end)
                put(self.root / 'rehearsal.json', rehearsal)
                with self.assertRaisesRegex(ValueError, 'command times'): self.check_full_fixture()

    def run_mocked_driver(self, loss_seconds=190.862634, baseline_exit=0):
        # Durations from actual7807 are regression INPUTS only. These temporary
        # receipts contain mocked commands; they never certify real G12 proof.
        clock = [0.0]
        durations = {'demo-baseline': 97.220724, 'demo-quic-basic': 57.037136,
                     'demo-loss': loss_seconds, 'demo-0rtt': 52.758191, 'cleanup': .073762}
        commands = []
        def run(command, **kwargs):
            commands.append(command)
            kwargs['stdout'].write('Synthetic mocked command; not real network evidence.\n')
            clock[0] += durations[command[1]]
            return SimpleNamespace(returncode=baseline_exit if command[1] == 'demo-baseline' else 0)
        def sleep(seconds): clock[0] += seconds
        stdout = sys.stdout
        try:
            with mock.patch.object(rehearsal_driver.os, 'setpgrp'), \
                    mock.patch.object(rehearsal_driver.signal, 'signal'), \
                    mock.patch.object(rehearsal_driver.time, 'monotonic', side_effect=lambda: clock[0]), \
                    mock.patch.object(rehearsal_driver.time, 'sleep', side_effect=sleep), \
                    mock.patch.object(rehearsal_driver.subprocess, 'run', side_effect=run), \
                    mock.patch.object(sys, 'stdout', io.StringIO()):
                try:
                    result = rehearsal_driver.main(self.root, self.base / 'backup')
                finally:
                    sys.stdout.log.close()
        finally:
            sys.stdout = stdout
        return result, commands

    def test_observed_durations_exclude_baseline_from_live_clock(self):
        result, commands = self.run_mocked_driver()
        self.assertEqual(result, 0)
        self.assertEqual([x[1] for x in commands], ['demo-baseline', 'demo-quic-basic', 'demo-loss', 'demo-0rtt', 'cleanup'])
        preparation = json.loads((self.root / 'preparation.json').read_text())
        self.assertAlmostEqual(preparation['elapsed_seconds'], 97.220724)
        live = json.loads((self.root / 'rehearsal.json').read_text())
        self.assertAlmostEqual(live['elapsed_seconds'], 360)
        gate.check_rehearsal(self.root, live)

    def test_slow_live_still_fails_original_seven_minute_limit(self):
        with self.assertRaisesRegex(ValueError, 'outside5–7min'):
            self.run_mocked_driver(loss_seconds=300)
        self.assertEqual(json.loads((self.root / 'preparation.json').read_text())['status'], 'PASS')
        live = json.loads((self.root / 'rehearsal.json').read_text())
        self.assertEqual(live['status'], 'FAIL')
        self.assertGreater(live['elapsed_seconds'], 420)

    def test_failed_baseline_stops_before_live_clock(self):
        with self.assertRaisesRegex(ValueError, 'baseline failed'):
            self.run_mocked_driver(baseline_exit=1)
        self.assertEqual(json.loads((self.root / 'preparation.json').read_text())['status'], 'FAIL')
        self.assertFalse((self.root / 'rehearsal.json').exists())


class G12OfflineEnvironmentTests(unittest.TestCase):
    def test_fresh_local_clone_reproduces_current_candidate_without_inherited_artifacts(self):
        with tempfile.TemporaryDirectory(prefix='g12-clone-unit-') as temporary:
            source = Path(temporary) / 'source'
            source.mkdir()
            (source / '.gitignore').write_text('/bin/\n/certs/*\n!/certs/.gitkeep\n/results/*\n!/results/.gitkeep\n/.tools/\n')
            for directory in ('certs', 'results'):
                (source / directory).mkdir()
                (source / directory / '.gitkeep').touch()
            (source / 'candidate.py').write_text('original fixture\n')
            (source / 'deleted.py').write_text('old tracked fixture\n')
            base_commit = fixture_commit(source)
            (source / 'candidate.py').write_text('modified review candidate\n')
            (source / 'deleted.py').unlink()
            (source / 'new.py').write_text('new untracked review candidate\n')
            (source / 'bin').mkdir()
            (source / 'bin/client').write_text('inherited application fixture\n')
            (source / 'certs/server.key').write_text('inherited private-key fixture\n')
            (source / 'results/old.json').write_text('inherited result fixture\n')
            for name in ('go1.27.1', 'gopath', 'analysis', 'tshark', 'gocache'):
                (source / '.tools' / name).mkdir(parents=True)
                (source / '.tools' / name / 'dependency-or-cache-fixture').touch()
            fresh = source / 'results/fresh-unit'
            fresh.mkdir()
            with mock.patch.object(reproduction, 'REPO', source):
                inventory = reproduction.export_source(fresh)
            env = reproduction.offline_environment(fresh)
            toplevel = subprocess.check_output(['git', '-C', str(fresh), 'rev-parse', '--show-toplevel'],
                                              env=env, text=True).strip()
            self.assertEqual(Path(toplevel), fresh)
            self.assertEqual(subprocess.check_output(['git', '-C', str(fresh), 'rev-parse', 'HEAD'],
                                                    env=env, text=True).strip(), base_commit)
            self.assertEqual((fresh / 'candidate.py').read_text(), 'modified review candidate\n')
            self.assertEqual((fresh / 'new.py').read_text(), 'new untracked review candidate\n')
            self.assertFalse((fresh / 'deleted.py').exists())
            self.assertEqual(set(inventory), {'.gitignore', 'candidate.py', 'new.py', 'certs/.gitkeep', 'results/.gitkeep'})
            self.assertTrue(all(gate.digest(fresh / name) == value for name, value in inventory.items()))
            self.assertFalse((fresh / 'bin').exists())
            self.assertEqual([p.name for p in (fresh / 'certs').iterdir()], ['.gitkeep'])
            self.assertEqual([p.name for p in (fresh / 'results').iterdir()], ['.gitkeep'])
            self.assertFalse((fresh / '.tools/gocache').exists())
            self.assertTrue(all((fresh / '.tools' / name).is_symlink()
                                for name in ('go1.27.1', 'gopath', 'analysis', 'tshark')))
            # Clone objects are separate from source objects (--no-local).
            for original in (source / '.git/objects').rglob('*'):
                copied = fresh / '.git/objects' / original.relative_to(source / '.git/objects')
                if original.is_file() and copied.is_file():
                    self.assertNotEqual(original.stat().st_ino, copied.stat().st_ino)

    def test_nested_export_cannot_inherit_parent_git_metadata(self):
        with tempfile.TemporaryDirectory(prefix='g12-vcs-unit-') as temporary:
            source = Path(temporary)
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            fresh = source / 'results/unit/fresh'
            fresh.mkdir(parents=True)
            inherited = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=fresh,
                                       text=True, capture_output=True)
            self.assertEqual(inherited.returncode, 0)
            self.assertEqual(Path(inherited.stdout.strip()), source)
            env = reproduction.offline_environment(fresh)
            isolated = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=fresh,
                                      env=env, text=True, capture_output=True)
            self.assertNotEqual(isolated.returncode, 0)
            self.assertEqual(env['GOPROXY'], 'off')
            self.assertEqual(env['GOCACHE'], str(fresh / '.tools/gocache'))

    def test_inherited_paths_and_evidence_variables_are_removed(self):
        with mock.patch.dict(os.environ, {'GOROOT': '/foreign/goroot', 'GOMODCACHE': '/foreign/modules',
                                         'GIT_DIR': '/foreign/.git', 'GIT_WORK_TREE': '/foreign',
                                         'QLOGDIR': '/foreign/qlogs'}):
            env = reproduction.offline_environment(Path('/tmp/synthetic-g12/fresh'))
        for name in ('GOROOT', 'GOMODCACHE', 'GIT_DIR', 'GIT_WORK_TREE', 'QLOGDIR'):
            self.assertNotIn(name, env)

    def test_owned_rehearsal_session_stops_without_signaling_unrelated_process(self):
        self.managed_group_case(leader_exits_early=False)

    def test_leader_exit143_still_waits_descendant_graceful_cleanup(self):
        self.managed_group_case(leader_exits_early=True)

    def managed_group_case(self, leader_exits_early):
        driver = (REPO / 'scripts/run-g12-review.sh').read_text()
        group_running = re.search(r'(?ms)^group_running\(\) \{\n.*?^\}', driver).group(0)
        cleanup = re.search(r'(?ms)^cleanup\(\) \{\n.*?^\}', driver).group(0)
        with tempfile.TemporaryDirectory(prefix='g12-signal-unit-') as temporary:
            root = Path(temporary)
            ready, stopped = root / 'ready', root / 'stopped'
            leaf_ready = root / 'leaf-ready'
            child_program = '''import json,os,signal,subprocess,sys,time
from pathlib import Path
os.setpgrp()
early=sys.argv[4]=='early'
leaf_program=''' + repr('''import signal,sys,time
from pathlib import Path
def stop(signum,frame):
 time.sleep(.3)
 Path(sys.argv[1]).write_text(str(signum))
 sys.exit(143)
signal.signal(signal.SIGTERM,stop)
Path(sys.argv[2]).write_text('ready')
while True:time.sleep(.1)
''') + '''
child=subprocess.Popen([sys.executable,'-c',leaf_program,sys.argv[2],sys.argv[3]])
while not Path(sys.argv[3]).exists():time.sleep(.01)
def stop(signum,frame):
 if not early:child.wait(timeout=3)
 sys.exit(143)
signal.signal(signal.SIGTERM,stop)
Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid(),'sid':os.getsid(0)}))
while True:time.sleep(.1)
'''
            shell = '\n'.join((
                'set -euo pipefail',
                'source ' + shlex.quote(str(REPO / 'scripts/process-lifecycle.sh')),
                group_running,
                cleanup,
                'python3 -c ' + shlex.quote(child_program) + ' ' + shlex.quote(str(ready)) + ' ' +
                shlex.quote(str(stopped)) + ' ' + shlex.quote(str(leaf_ready)) +
                (' early &' if leader_exits_early else ' waits &'),
                'rehearsal_pid=$!',
                'for ((i=0;i<60;i++)); do [[ ! -e ' + shlex.quote(str(ready)) + ' ]] || break; sleep .05; done',
                '[[ -e ' + shlex.quote(str(ready)) + ' ]]',
                'trap cleanup EXIT',
                'exit 143',
            ))
            unrelated = subprocess.Popen(['sleep', '30'], start_new_session=True)
            try:
                result = subprocess.run(['bash', '-c', shell], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 143, result.stderr)
                self.assertEqual(stopped.read_text(), str(signal.SIGTERM))
                self.assertEqual(json.loads(ready.read_text())['sid'], os.getsid(0),
                                 'rehearsal changed the original terminal session')
                self.assertIsNone(unrelated.poll(), 'cleanup signaled an unrelated process')
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=3)
                if ready.exists():
                    pid = json.loads(ready.read_text())['pid']
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == '__main__':
    unittest.main()
