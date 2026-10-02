#!/usr/bin/env python3
"""Unprivileged evidence preparation, file sinks and lifecycle records."""
import hashlib,json,os,re,shutil,struct,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
from build import load_verified

def now():return datetime.now(timezone.utc).isoformat()
def put(p,obj):Path(p).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def pcap_packets(path):
 """Check classic PCAP record boundaries without loading packet payloads."""
 with Path(path).open('rb') as f:
  size=os.fstat(f.fileno()).st_size;header=f.read(24)
  if len(header)!=24:raise ValueError('truncated PCAP header')
  orders={b'\xd4\xc3\xb2\xa1':'<',b'\xa1\xb2\xc3\xd4':'>',b'\x4d\x3c\xb2\xa1':'<',b'\xa1\xb2\x3c\x4d':'>'}
  order=orders.get(header[:4])
  if not order:raise ValueError('unsupported PCAP magic')
  major,minor,_,_,snaplen,_=struct.unpack(order+'HHIIII',header[4:])
  if (major,minor)!=(2,4) or not 0<snaplen<=16777216:raise ValueError('invalid PCAP header')
  count=0
  while f.tell()<size:
   packet=f.read(16)
   if len(packet)!=16:raise ValueError('truncated PCAP record')
   _,_,included,original=struct.unpack(order+'IIII',packet)
   if included>snaplen or included>original or included>size-f.tell():raise ValueError('truncated/invalid PCAP payload')
   f.seek(included,1);count+=1
  return count

def capture_status(out,ns,original,cleanup):
 p=Path(out);log=(p/'tcpdump.log').read_text()
 captured=re.search(r'(\d+) packets? captured',log)
 dropped=re.search(r'(\d+) packets? dropped by kernel',log)
 error='';count=None
 try:count=pcap_packets(p/'capture.pcap')
 except (OSError,ValueError) as e:error=str(e)
 complete=not error and count is not None and count>0 and captured is not None and int(captured[1])==count and dropped is not None and int(dropped[1])==0
 if not complete and not error:error='empty PCAP, tcpdump count/footer mismatch or capture drops'
 return dict(namespace=ns,interface='eth0',point='AF_PACKET tap; eth0 ingress may precede IFB impairment, corroborate kernel ACK/qlog receive',uid=os.getuid(),original_exit=int(original),cleanup_exit=int(cleanup) if complete else 1,capture_packets=count,capture_complete=complete,capture_error=error,capture_drops=int(dropped[1]) if dropped else None,log=log)

def main():
 if os.getuid()==0:raise ValueError('file/analysis owner must be ordinary user')
 op,*args=sys.argv[1:]
 if op=='sink':
  with open(args[0],'xb',buffering=0) as f:
   while chunk:=sys.stdin.buffer.read1(65536):
    remaining=memoryview(chunk)
    while remaining:
     n=f.write(remaining)
     if not n:raise OSError('capture sink made no write progress')
     remaining=remaining[n:]
   os.fsync(f.fileno())
 elif op=='capture-status':
  out,ns,original,cleanup=args;status=capture_status(out,ns,original,cleanup)
  put(Path(out)/'status.json',status)
  if status['cleanup_exit']!=0:raise ValueError(status['capture_error'] or 'capture cleanup failed')
 elif op=='prepare':
  root=Path(args[0]);root.mkdir()
  receipt=load_verified(REPO/'bin/build.json');shutil.copyfile(REPO/'bin/build.json',root/'build.json')
  for d in ('logs','network','host','probes','runs','traces','captures','viewers','config'): (root/d).mkdir()
  for source in ('configs/workloads.json','configs/scenarios.json','certs/server.crt','schemas/result-records.schema.json'):shutil.copyfile(REPO/source,root/'config'/Path(source).name)
  sources={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for d in ('internal','cmd','scripts','analysis','tests','configs','schemas') for p in (REPO/d).rglob('*') if p.is_file() and p.suffix in ('.go','.py','.sh','.json','.txt')}
  sources.update(receipt['inputs'])
  put(root/'source-hashes.json',sources)
  seed_disabled=os.environ.get('NETEM_SEED')=='none'
  planned=[dict(run_id='handshake_'+m,profile='handshake',transport='quic',mode=m,scenario='rtt50-loss0',seed=None if seed_disabled else 2026100200) for m in ('cold','resumed','early')]
  planned.extend(dict(run_id=f'loss_{i}_{tr}',profile='bulk',transport=tr,mode='cold',scenario='rtt50-loss3',seed=None if seed_disabled else 2026100201+i) for i in range(10) for tr in (('tcp','quic') if i%2==0 else ('quic','tcp')))
  put(root/'manifest.json',dict(schema_version=1,experiment_id=root.name,trace_mode='evidence',performance_pooling=False,created_utc=now(),uid=os.getuid(),gid=os.getgid(),kernel=subprocess.check_output(['uname','-a'],text=True).strip(),distribution=Path('/etc/os-release').read_text(),resources=Path('/proc/meminfo').read_text(),host_os='Windows 11 user-reported D13',execution_layer='Ubuntu WSL2',wsl_version='unknown: Windows CLI not queried',build=receipt,decoder=subprocess.check_output(['bash',str(REPO/'scripts/tshark.sh'),'-v'],text=True),runs=[],planned_runs=planned,config_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'config').iterdir()},attempt_policy='exactly ten TCP/QUIC loss pairs; all attempts retained; first qualifying pair selected; insufficient causality stays INCONCLUSIVE'))
 elif op=='run':
  root,rid,profile,tr,mode,scenario,seed,exit_code=args;root=Path(root)
  m=json.loads((root/'manifest.json').read_text())
  matches=[r for r in m['runs'] if r['run_id']==rid]
  if exit_code!='pending':
   if len(matches)!=1 or matches[0]['exit_code'] is not None:raise ValueError('invocation completion mismatch')
   matches[0].update(exit_code=int(exit_code),ended_utc=now());put(root/'manifest.json',m);return
  if matches:raise ValueError('duplicate evidence invocation')
  m['runs'].append(dict(run_id=rid,profile=profile,transport=tr,mode=mode,scenario=scenario,seed=None if seed=='none' else int(seed),exit_code=None,started_utc=now(),ended_utc=None,out='runs/'+rid,client_qlog='traces/'+rid+'/client-qlog',server_qlog='traces/'+rid+'/server-qlog',client_keylog='traces/'+rid+'/client.keylog',server_keylog='traces/'+rid+'/server.keylog',captures='captures/'+rid))
  put(root/'manifest.json',m)
 elif op=='cleanup':
  root,original,clean=args;put(Path(root)/'cleanup.json',dict(original_exit=int(original),cleanup_exit=int(clean),finished_utc=now()))
 else:raise ValueError('unknown evidence operation')
if __name__=='__main__':main()
