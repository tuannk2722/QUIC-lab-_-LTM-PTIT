#!/usr/bin/env python3
"""Actual localhost qlog/progress/TLS checks. No namespace/PCAP/HOL claims."""
import json,os,socket,subprocess,tempfile,time
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]

def main():
 if os.getuid()==0:raise ValueError('apps must be unprivileged')
 os.chdir(REPO)
 root=Path(tempfile.mkdtemp(prefix='p11-software-',dir=REPO/'results'))
 print('software_root='+str(root),flush=True)
 env=dict(os.environ);env.pop('QLOGDIR',None)
 records=[]
 import sys,shutil,hashlib
 sys.path.insert(0,str(REPO/"scripts"));from build import load_verified
 receipt=load_verified(REPO/"bin/build.json");shutil.copyfile(REPO/"bin/build.json",root/"build.json")
 sources={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for d in ("internal","scripts","analysis","tests") for p in (REPO/d).rglob("*") if p.is_file() and p.suffix in (".go",".py",".sh",".json",".txt")}
 sources.update(receipt["inputs"])
 (root/"source-hashes.json").write_text(json.dumps(sources,indent=2)+"\n")
 for profile,tr,modes in [('handshake','quic',['cold','resumed','early']),('bulk','quic',['cold']),('bulk','tcp',['cold'])]:
  case=root/(profile+'-'+tr);case.mkdir();ready=case/'ready'; server=None
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  with (case/'server.log').open('x') as log:
   server=subprocess.Popen(['bin/server',f'--transport={tr}',f'--profile={profile}',f'--listen=127.0.0.1:{port}',f'--ready-file={ready}',f'--qlog-dir={case}/server-qlog',f'--keylog={case}/server.keylog'],stdout=log,stderr=subprocess.STDOUT,env=env)
  try:
   for _ in range(100):
    if ready.exists():break
    if server.poll() is not None:raise ValueError('server startup failed: '+(case/'server.log').read_text())
    time.sleep(.05)
   if not ready.exists():raise ValueError('readiness timeout')
   for mode in modes+(['tls_failure'] if tr=='tcp' else []):
    fail=mode=='tls_failure';actual_mode='cold' if fail else mode
    rid=f'{profile}_{tr}_{mode}';out=case/mode
    args=['bin/client',f'--transport={tr}',f'--profile={profile}',f'--mode={actual_mode}',f'--addr=127.0.0.1:{port}','--server-name=wrong.invalid' if fail else '--server-name=localhost','--experiment-id=g11software',f'--run-id={rid}',f'--out={out}',f'--qlog-dir={case}/{mode}-qlog',f'--keylog={case}/{mode}.keylog','--progress','--format=json']
    with (case/(mode+'.log')).open('x') as log:rc=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=90).returncode
    records.append(dict(run_id=rid,profile=profile,transport=tr,mode=actual_mode,out=str(out.relative_to(root)),client_qlog=str((case/(mode+'-qlog')).relative_to(root)),server_qlog=str((case/'server-qlog').relative_to(root)),exit_code=rc,argv=args))
    if rc!=(1 if fail else 0):raise ValueError((case/(mode+'.log')).read_text())
  finally:
   server.terminate()
   try:rc=server.wait(timeout=15)
   except subprocess.TimeoutExpired:server.kill();server.wait();raise ValueError('forced server stop')
   if rc or ready.exists():raise ValueError('server shutdown failed')
 data=dict(schema_version=1,scope='localhost correctness only; no captured packet or impairment proof',trace_mode='evidence',uid=os.getuid(),build=receipt,runs=records)
 (root/'manifest.json').write_text(json.dumps(data,indent=2)+'\n')
 print(json.dumps(data,indent=2))
 return root
if __name__=='__main__':main()
