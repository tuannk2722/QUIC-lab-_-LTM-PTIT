#!/usr/bin/env python3
"""Archived G11 audit. Preserve every attempt; select by causal criteria only."""
import hashlib,json,os,re,sys
from pathlib import Path
from datetime import datetime
REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'analysis'),str(REPO/'scripts'),str(REPO/'tests/system')]
from evidence import check_progress,correlated,early_qlog,viewer,render_timeline
from packet_evidence import decode,early_packet_proof
from hol import tcp_candidate,quic_candidate
from check_g10 import check_kernel
from check_g08 import netem,probe
from validate import require

def read(p):return json.loads(Path(p).read_text())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def audit_capture(root,run,ns,uid):
 cap=root/run['captures']/ns;status=read(cap/'status.json')
 require(status['uid']==uid and status['namespace']==ns and status['interface']=='eth0' and status['cleanup_exit']==0 and status['original_exit'] in (0,130,143) and status['capture_drops']==0,'capture lifecycle/drop failed')
 # Audit bytes/footer even for historical receipts, without rewriting them.
 from importlib.util import spec_from_file_location,module_from_spec
 spec=spec_from_file_location('capture_support',REPO/'scripts/evidence-support.py');support=module_from_spec(spec);spec.loader.exec_module(support)
 actual=support.capture_status(cap,ns,status['original_exit'],status['cleanup_exit'])
 require(actual['capture_complete'] and actual['cleanup_exit']==0,'capture incomplete: '+actual['capture_error'])
 if 'capture_packets' in status:require(status['capture_packets']==actual['capture_packets'] and status['capture_complete'] is True,'capture status/bytes differ')
 return cap

def check_early(root):
 """Fail early after handshake captures; this is never a full G11 PASS."""
 root=Path(root);manifest=read(root/'manifest.json')
 require(manifest['uid']>0 and manifest['trace_mode']=='evidence','evidence mode/UID invalid')
 run=next(r for r in manifest['runs'] if r['run_id']=='handshake_early')
 require(run['exit_code']==0,'early transfer failed')
 record,_=check_progress(root/run['out'])
 pairs=correlated(root/run['client_qlog'],root/run['server_qlog'],run['run_id'])
 require(len(pairs)==2,'ticket/target early trace count differs')
 api=early_qlog(pairs,record);target=next(p for p in pairs if p['role']=='target')
 require(api['status']=='PASS','early API/qlog not qualified')
 key=root/run['client_keylog']
 require(key.stat().st_mode&0o777==0o600,'secret permissions differ')
 require(any(line.startswith('CLIENT_EARLY_TRAFFIC_SECRET ') for line in key.read_text().splitlines()),'missing CLIENT_EARLY_TRAFFIC_SECRET; build with make build')
 proofs={}
 for ns in ('qclient','qserver'):
  cap=audit_capture(root,run,ns,manifest['uid'])
  proofs[ns]=early_packet_proof(decode(cap/'capture.pcap',key,cap/'decoded'),target,record,api)
  require(proofs[ns]['status']=='PASS','accepted 0RTT REQUEST not corroborated in '+ns)
 status=dict(status='PASS',scope='handshake early packet precheck only; full23 G11 pending',run_id=run['run_id'],proofs=proofs)
 (root/'early-packet-check.json').write_text(json.dumps(status,indent=2)+'\n')
 print(json.dumps(status,indent=2))
 return status

def network(root,run):
 rid=run['run_id'];before=read(root/'network'/f'{rid}.before.json');after=read(root/'network'/f'{rid}.after.json')
 for s in (before,after):
  check_kernel(s);require(s['scenario']==run['scenario'] and s['netem_seed']==run['seed'],'evidence network differs')
 for k in ('client_namespace_id','server_namespace_id','config_sha256','delay_each_way_ms','loss_downstream_pct','loss_upstream_pct','rate_mbps'):
  require(before[k]==after[k],'network changed during trial: '+k)
 expected={'rtt50-loss0':(25,0,0,20),'rtt50-loss3':(25,3,0,20)}[run['scenario']]
 require(tuple(before[k] for k in ('delay_each_way_ms','loss_downstream_pct','loss_upstream_pct','rate_mbps'))==expected,'wrong scenario parameters')
 require(before['config_sha256']==read(root/'manifest.json')['config_sha256']['scenarios.json'],'actual kernel config differs from archived config')
 deltas={}
 for ns in ('qclient','qserver'):
  b,a=netem(before,ns),netem(after,ns)
  d={k:a[k]-b[k] for k in ('packets','bytes','drops','overlimits')};require(all(v>=0 for v in d.values()),'counter reset during evidence')
  pattern=r'Sent (\d+) bytes (\d+) pkt';bs=re.findall(pattern,before['observation'][ns]['filters_text']);ats=re.findall(pattern,after['observation'][ns]['filters_text'])
  require(len(bs)==len(ats)==1 and int(ats[0][1])>int(bs[0][1]) and d['packets']>0,'missing redirect/IFB traffic')
  deltas[ns]=d
 from importlib.util import spec_from_file_location,module_from_spec
 spec=spec_from_file_location('support',REPO/'scripts/bench-support.py');support=module_from_spec(spec);spec.loader.exec_module(support)
 idle_files=list((root/'network').glob(rid+'.idle-*-before.json'))
 idle_files.sort(key=lambda p:int(p.name.split('.idle-')[1].split('-')[0]))
 require(idle_files and [int(p.name.split('.idle-')[1].split('-')[0]) for p in idle_files]==list(range(len(idle_files))),'idle observation chronology/inventory differs')
 previous=datetime.fromisoformat(after['timestamp_utc'])
 for p in idle_files:
  other=p.with_name(p.name.replace('-before','-after'));ib,ia=read(p),read(other)
  for snapshot in (ib,ia):
   check_kernel(snapshot)
   for k in ('scenario','netem_seed','config_sha256','client_namespace_id','server_namespace_id'):require(snapshot[k]==before[k],'idle identity/config changed')
  bt,at=[datetime.fromisoformat(s['timestamp_utc']) for s in (ib,ia)]
  require(previous<=bt<=at,'idle timestamps reversed');previous=at
 support.idle(idle_files[-1],idle_files[-1].with_name(idle_files[-1].name.replace('-before','-after')))
 deltas['accepted_idle_utc']=previous.isoformat()
 return deltas

def check(root,software=False):
 root=Path(root);manifest=read(root/'manifest.json');require(manifest['trace_mode']=='evidence' and manifest['uid']>0,'evidence mode/UID invalid')
 software=software or manifest.get('scope','').startswith('localhost')
 if 'build' in manifest:
  require(read(root/'build.json')==manifest['build'],'receipt/manifest differs')
  sources=read(root/'source-hashes.json')
  require(all(sources.get(p)==h for p,h in manifest['build']['inputs'].items()),'as-run source/receipt differs')
 if not software:
  for name,h in manifest['config_sha256'].items():require(digest(root/'config'/name)==h,'archived config hash differs')
  require(len(manifest['planned_runs'])==23,'planned denominator differs')
  require(manifest['performance_pooling'] is False,'instrumented cohort pooled with performance')
 results=[];last_idle=None;view_dir=root/('viewers');view_dir.mkdir(exist_ok=True)
 for run in manifest['runs']:
  rid=run['run_id'];record,rows=check_progress(root/run['out']);r=record['run']
  require(r['trace_mode']==r['phase']=='evidence' and r['run_id']==rid and r['mode']==run['mode'] and r['transport']==run['transport'],'trace labels/FK differ')
  require((run['exit_code']==0)==r['success'] and run['exit_code'] in (0,1),'exit/outcome differs')
  expected=(1,1024,1024) if run['profile']=='handshake' else (6,1048576,16384)
  require((r['resource_count'],r['resource_size_bytes'],r['chunk_bytes'])==expected,'workload differs')
  result=dict(run_id=rid,success=r['success'],progress_points=len(rows),mode=run['mode'],transport=run['transport'],profile=run['profile'])
  pairs=[]
  if run['transport']=='quic':
   try:pairs=correlated(root/run['client_qlog'],root/run['server_qlog'],rid)
   except (ValueError,OSError,KeyError,StopIteration) as e:
    if r['success']:raise
    result['trace_failure_diagnostic']=str(e)
   if r['success']:require(len(pairs)==(1 if run['mode']=='cold' else 2),'ticket/target trace count differs')
   result['qlog_connections']=[{k:p[k] for k in ('role','odcid','client_file','server_file','client_endpoint','server_endpoint')} for p in pairs]
   viewer(view_dir/(rid+'.html'),pairs,rows,rid);render_timeline(view_dir/(rid+'.png'),pairs,rows,rid)
  else:
   viewer(view_dir/(rid+'.html'),[],rows,rid);render_timeline(view_dir/(rid+'.png'),[],rows,rid)
  if run['mode']=='early':result['early_qlog']=early_qlog(pairs,record)
  if not software:
   require(r['network_profile']=='ingress-ifb' and r['scenario']==run['scenario'] and r['netem_seed']==run['seed'],'applied labels differ')
   result['network_counters']=network(root,run)
   before=read(root/'network'/f'{rid}.before.json');after=read(root/'network'/f'{rid}.after.json')
   bt,at=[datetime.fromisoformat(s['timestamp_utc']) for s in (before,after)]
   if last_idle:require(last_idle<=bt,'reset before prior accepted idle')
   require(bt<=datetime.fromisoformat(r['timestamp_utc'])<=datetime.fromisoformat(run['ended_utc'])<=at,'trial/network chronology differs')
   last_idle=datetime.fromisoformat(result['network_counters']['accepted_idle_utc'])
   packets=[]
   for ns in ('qclient','qserver'):
    cap=audit_capture(root,run,ns,manifest['uid'])
    key=root/run['client_keylog'];require(key.stat().st_mode&0o777==0o600 and (root/run['server_keylog']).stat().st_mode&0o777==0o600,'secret permissions differ')
    decoded=decode(cap/'capture.pcap',key,cap/'decoded')
    for p in decoded:p['capture_namespace']=ns
    packets.extend(decoded)
   packets.sort(key=lambda p:p['epoch'])
   if run['transport']=='quic':
    require(any(p.get('quic') and p['packet_type']==0 for p in packets) and any(p.get('quic') and p['packet_number'] is not None and p['streams'] for p in packets),'QUIC UDP decoding lacks initial or decrypted STREAM')
    result['udp_decode']='PASS'
    if run['mode']=='early':
     target=next(p for p in pairs if p['role']=='target');result['early_packet']=early_packet_proof(packets,target,record,result['early_qlog'])
    if run['profile']=='bulk':result['hol']=quic_candidate(next(p for p in pairs if p['role']=='target'),record,rows) if pairs else dict(status='INCONCLUSIVE',reason='failed transfer has no correlated target trace')
   else:
    require(any(p['protocol']=='tcp' and p['length']>0 for p in packets),'TCP capture empty')
    result['hol']=tcp_candidate(packets,record,rows)
  else:
   result['pcap']='BLOCKED: not captured in localhost software gate'
   if run['profile']=='bulk':result['hol']=dict(status='NOT_RUN',reason='software correctness has no impaired paired captures')
  results.append(result)
 early=next(r for r in results if r['mode']=='early')
 status=dict(gate='G11',status='BLOCKED' if software else 'PASS',scope='localhost software only' if software else 'actual ingress IFB evidence',qlog='PASS',progress='PASS',udp_decode='BLOCKED' if software else 'PASS',early_proof='BLOCKED' if software else early['early_packet']['status'],runs=results,representative=None,hol='NOT_RUN' if software else 'INCONCLUSIVE',full_demo_complete=False)
 if not software:
  require(manifest['planned_runs']==[{k:r[k] for k in ('run_id','profile','transport','mode','scenario','seed')} for r in manifest['runs']],'invocation order differs from planned attempts')
  require(len(results)==23,'must retain three handshake and ten paired HOL attempts')
  require({r['run_id'] for r in results}=={'handshake_'+m for m in ('cold','resumed','early')}|{f'loss_{i}_{tr}' for i in range(10) for tr in ('tcp','quic')},'attempt inventory differs')
  require(all(r['success'] for r in results if r['profile']=='handshake'),'handshake evidence transfer failed')
  require(status['early_proof']=='PASS','accepted 0RTT REQUEST not corroborated')
  for i in range(10):
   pair=[next(r for r in results if r['run_id']==f'loss_{i}_{tr}') for tr in ('tcp','quic')]
   if all(r['success'] and r['hol']['status']=='PASS' for r in pair):status.update(hol='PASS',representative=[r['run_id'] for r in pair],full_demo_complete=True);break
  cleanup=read(root/'cleanup.json');require(cleanup['original_exit']==cleanup['cleanup_exit']==0,'cleanup failed')
  for kind in ('link','address','route'):
   before=(root/'host'/f'{kind}.before.json').read_bytes()
   require(before==(root/'host'/f'{kind}.active.json').read_bytes()==(root/'host'/f'{kind}.final.json').read_bytes(),'host state changed')
  require((root/'network/cleanup.json').exists() and read(root/'network/cleanup.json')['verified'] is False,'netem cleanup absent')
  for scenario in ('baseline','rtt50-loss0'):
   check_kernel(read(root/'network'/f'{scenario}-probe.json'))
   for ns in ('qclient','qserver'):probe(root/'probes'/f'{scenario}-{ns}.log',scenario,ns)
 # Store hashes of public evidence. Keylogs stay local and out of archives/git.
 status['counts']=dict(n_planned=len(manifest.get('planned_runs',manifest['runs'])),n_invoked=len(results),n_success=sum(r['success'] for r in results),n_failed=sum(not r['success'] for r in results))
 notes=['# Annotated G11 evidence', '', 'Instrumentation is enabled; these runs are excluded from main performance. All attempts are retained.', '', 'Progress is cumulative validated payload at 16 KiB thresholds; points inside one frame share its completion time. Qlog references and client t0 are distinct clocks.', '', 'Receiver eth0 AF_PACKET may observe bytes before IFB loss: use TCP cumulative ACK/SACK or client qlog receive to establish actual reception.', '', 'Selected HOL pair: '+str(status['representative'])+'; HOL status: '+status['hol']+'. Full demo complete: '+str(status['full_demo_complete'])+'.', '', 'Early REQUEST proof: '+status['early_proof']+'. Qlog STREAM range alone does not expose payload content.', '']
 for result in results:
  notes.append('- '+result['run_id']+': success='+str(result['success'])+', payload points='+str(result['progress_points'])+'; [local viewer](viewers/'+result['run_id']+'.html), [timeline](viewers/'+result['run_id']+'.png).')
  for key in ('early_qlog','early_packet','hol'):
   if key in result:notes.append('  '+key+': '+json.dumps(result[key],sort_keys=True))
 (root/'evidence-notes.md').write_text('\n'.join(notes)+'\n')
 status['artifact_sha256']={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and p.suffix!='.keylog' and p.name!='g11-check.json'}
 (root/'g11-check.json').write_text(json.dumps(status,indent=2)+'\n')
 print(json.dumps({k:v for k,v in status.items() if k not in ('runs','artifact_sha256')},indent=2))
 return status
if __name__=='__main__':
 try:
  if '--early-only' in sys.argv[2:]:check_early(sys.argv[1])
  else:check(sys.argv[1], '--software' in sys.argv[2:])
 except (OSError,ValueError,KeyError,TypeError,StopIteration,AssertionError) as e:
  root=Path(sys.argv[1]);(root/'g11-failure.json').write_text(json.dumps(dict(gate='G11',status='FAIL',error=str(e)),indent=2)+'\n')
  print('G11 FAIL:',e,file=sys.stderr);sys.exit(1)
