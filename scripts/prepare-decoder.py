#!/usr/bin/env python3
"""Reproduce the optional local decoder from pinned Ubuntu archive packages."""
import hashlib,json,os,subprocess
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
if os.getuid()==0:raise SystemExit('Run decoder preparation as ordinary user')
lock=json.loads((REPO/'analysis/decoder-packages.json').read_text())
root=REPO/'.tools/tshark';debs=root/'debs';target=root/'root';debs.mkdir(parents=True,exist_ok=True);target.mkdir(exist_ok=True)
for item in lock['packages']:
 p=debs/item['file']
 if not p.exists():subprocess.run(['apt-get','download',item['package']+'='+item['version']],cwd=debs,check=True)
 if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('Decoder archive hash mismatch: '+p.name)
 subprocess.run(['dpkg-deb','-x',str(p),str(target)],check=True)
subprocess.run(['bash',str(REPO/'scripts/tshark.sh'),'-v'],check=True)
