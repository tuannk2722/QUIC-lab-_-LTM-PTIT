#!/usr/bin/env python3
"""Timed offline terminal walkthrough; records commands, not human oral delivery."""
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def walkthrough(run, wait_until, announce=print):
    """DEMO_SPEC live A→C→B; baseline acceptance is prepared beforehand."""
    announce('0:00 topology: qclient 10.10.0.1 -> veth/receiver IFB -> qserver 10.10.0.2; same RAM bytes/certificate.', flush=True)
    announce('Show docs/REPORT.md environment and workload. Each demo manages its server and retains real evidence.', flush=True)
    wait_until(25)
    run('basic', 'demo-quic-basic')
    announce('UDP4433 and decoded QUIC: open demos/basic/demo-check.json and viewer. Encrypted payload needs local keylog.', flush=True)
    wait_until(95)
    run('loss', 'demo-loss')
    announce('One TCP connection/six resources; QUIC one connection/six streams. Read HOL status; if inconclusive use labeled saved G11 pair.', flush=True)
    wait_until(195)
    run('0rtt', 'demo-0rtt')
    announce('Cold/resumed/early, ticket warmups separate. Check actual DidResume/Used0RTT AND packet REQUEST proof; fallback is not accepted early.', flush=True)
    wait_until(255)
    run('cleanup', 'cleanup')
    announce('Open docs/REPORT.md and results/g12-analysis main plots: attempted/success/failure, median/p95; no pooling correlated streams.', flush=True)
    wait_until(310)
    announce('Limitations: shared WSL kernel/CPU, TCP CUBIC vs QUIC Reno, scheduler/packetization, configured downstream loss affects control packets too.', flush=True)
    announce('This is a timed terminal walkthrough. The team still reviews code ownership, spoken delivery and slide submission.', flush=True)
    wait_until(360)


def main(root, backup):
    if os.getuid() == 0:
        raise ValueError('rehearsal/Make/file owner must be unprivileged')
    os.setpgrp()  # Own descendants, retain original controlling terminal/session.
    software = json.loads((root / 'software.json').read_text())
    if software['status'] != 'PASS' or software['uid'] != os.getuid():
        raise ValueError('fresh software reproduction must PASS for this owner')
    class TeeOutput:
        def __init__(self):
            self.terminal = sys.stdout
            self.log = (root / 'logs/walkthrough.log').open('x')

        def write(self, value):
            self.log.write(value)
            return self.terminal.write(value)

        def flush(self):
            self.log.flush()
            self.terminal.flush()

    sys.stdout = TeeOutput()
    fresh = Path(software['fresh_root'])
    (root / 'demos').mkdir()
    phase = 'preparation'
    started = time.monotonic()
    record = dict(schema_version=1, status='IN_PROGRESS', uid=os.getuid(), steps=[],
                  started_utc=datetime.now(timezone.utc).isoformat(), offline=True,
                  scope='baseline Make acceptance before live A→C→B clock')
    env = dict(os.environ)
    env.pop('QLOGDIR', None)
    env.update(GOPROXY='off', GOSUMDB='off', GOTOOLCHAIN='local', GIT_CEILING_DIRECTORIES=str(fresh.parent))

    def save():
        record['elapsed_seconds'] = time.monotonic() - started
        (root / (phase + '.json')).write_text(json.dumps(record, indent=2) + '\n')

    def wait_until(seconds):
        while time.monotonic() - started < seconds:
            time.sleep(min(1, seconds - (time.monotonic() - started)))

    def run(label, target):
        command = ['make', target]
        if label != 'cleanup':
            command += ['DEMO_OUT=' + str(root / 'demos' / label), 'DEMO_BACKUP=' + str(backup)]
        log = root / 'logs' / (phase + '-' + label + '.log')
        start = time.monotonic() - started
        print(f'G12 {phase}: {label}, elapsed={start:.1f}s, log={log}', flush=True)
        with log.open('x') as target:
            rc = subprocess.run(command, cwd=fresh, env=env, stdout=target, stderr=subprocess.STDOUT).returncode
        record['steps'].append(dict(name=label, argv=command, exit=rc,
                                    start_seconds=start, end_seconds=time.monotonic()-started,
                                    log=str(log.relative_to(root)), sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
        save()
        if rc:
            raise ValueError(f'{label} failed with exit {rc}; see {log}')

    def interrupted(signum, _frame):
        raise KeyboardInterrupt('rehearsal interrupted by signal ' + str(signum))

    signal.signal(signal.SIGTERM, interrupted)
    save()
    try:
        print('G12 preparation: mandatory baseline target runs before the live clock; artifacts and timing remain recorded.', flush=True)
        run('baseline', 'demo-baseline')
        record.update(status='PASS', finished_utc=datetime.now(timezone.utc).isoformat())
        save()
        preparation_digest = hashlib.sha256((root / 'preparation.json').read_bytes()).hexdigest()
        phase = 'rehearsal'
        started = time.monotonic()
        record = dict(schema_version=2, status='IN_PROGRESS', uid=os.getuid(), steps=[],
                      started_utc=datetime.now(timezone.utc).isoformat(), offline=True,
                      preparation=dict(path='preparation.json', sha256=preparation_digest),
                      presentation_policy='timed terminal walkthrough; human oral delivery not certified')
        save()
        walkthrough(run, wait_until)
        elapsed = time.monotonic() - started
        if not 300 <= elapsed <= 420:
            raise ValueError(f'walkthrough outside5–7min: {elapsed:.3f}s')
        record.update(status='PASS', finished_utc=datetime.now(timezone.utc).isoformat())
    except KeyboardInterrupt:
        record.update(status='FAIL', error=phase + ' interrupted; inspect demo cleanup receipts')
        save()
        return 130
    except (OSError, ValueError) as error:
        record.update(status='FAIL', error=str(error))
        save()
        raise
    save()
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('backup', type=Path)
    args = parser.parse_args()
    try:
        sys.exit(main(args.root.resolve(), args.backup.resolve()))
    except (OSError, ValueError, KeyError) as error:
        print('G12 rehearsal FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
