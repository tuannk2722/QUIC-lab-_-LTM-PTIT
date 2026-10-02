#!/usr/bin/env python3
"""Go1.27.1 build-only keylog fix; never edit GOROOT or derive secrets.

Go already computes these secrets for QUIC. The overlay only forwards them to
the existing Config.writeKeyLog (a no-op when KeyLogWriter is nil).
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

VERSION = 'go1.27.1'
REPO = Path(__file__).resolve().parents[1]
PATCHES = {
    'src/crypto/tls/handshake_client.go': (
        'ae3719b4cd6925b3e2689a21422865ce99611d097d727f9dc939c031f0ea703b',
        '\t\tc.quicSetWriteSecret(QUICEncryptionLevelEarly, suite.id, earlyTrafficSecret)',
        '\t\tif err := c.config.writeKeyLog("CLIENT_EARLY_TRAFFIC_SECRET", transcriptHello.random, earlyTrafficSecret); err != nil {\n'
        '\t\t\tc.sendAlert(alertInternalError)\n\t\t\treturn err\n\t\t}\n'),
    'src/crypto/tls/handshake_server_tls13.go': (
        '6cb325a7623c3bfe60e066b08fed2cc64e6b6cff85ad8f6467c038968d3a7fe6',
        '\t\t\tif err := c.quicSetReadSecret(QUICEncryptionLevelEarly, hs.suite.id, earlyTrafficSecret); err != nil {',
        '\t\t\tif err := c.config.writeKeyLog("CLIENT_EARLY_TRAFFIC_SECRET", hs.clientHello.random, earlyTrafficSecret); err != nil {\n'
        '\t\t\t\tc.sendAlert(alertInternalError)\n\t\t\t\treturn err\n\t\t\t}\n'),
}


def patched_sources(goroot):
    sources, receipt = {}, {}
    for relative, (expected, anchor, insertion) in PATCHES.items():
        original = (Path(goroot) / relative).read_bytes()
        actual = hashlib.sha256(original).hexdigest()
        if actual != expected:
            raise ValueError(f'{relative}: pinned Go source hash differs; refusing overlay')
        source = original.decode()
        if source.count(anchor) != 1:
            raise ValueError(f'{relative}: early-secret anchor is not unique')
        replacement = source.replace(anchor, insertion + anchor).encode()
        sources[relative] = replacement
        receipt[relative] = dict(original_sha256=actual, overlay_sha256=hashlib.sha256(replacement).hexdigest())
    return sources, receipt


def prepare(go, destination=None):
    if os.getuid() == 0:
        raise ValueError('prepare the build overlay as an ordinary user')
    version = subprocess.check_output([go, 'version'], text=True).split()[2]
    if version != VERSION:
        raise ValueError(f'expected {VERSION}, got {version}')
    goroot = Path(subprocess.check_output([go, 'env', 'GOROOT'], text=True).strip()).resolve()
    sources, receipt = patched_sources(goroot)
    destination = Path(destination or REPO / '.tools/tls-keylog-overlay').resolve()
    destination.mkdir(parents=True, exist_ok=True)
    mapping = {}
    for relative, source in sources.items():
        target = destination / Path(relative).name
        target.write_bytes(source)
        mapping[str(goroot / relative)] = str(target)
    overlay = destination / 'overlay.json'
    overlay.write_text(json.dumps({'Replace': mapping}, indent=2) + '\n')
    provenance = dict(kind='go-build-overlay', go_version=VERSION,
                      scope='existing QUIC early secret to optional KeyLogWriter; no cryptography changes',
                      files=receipt)
    (destination / 'receipt.json').write_text(json.dumps(provenance, indent=2) + '\n')
    return overlay, provenance


if __name__ == '__main__':
    try:
        overlay, receipt = prepare(sys.argv[1])
        print(json.dumps(dict(overlay=str(overlay), **receipt), indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'TLS keylog overlay: {exc}', file=sys.stderr)
        sys.exit(1)
