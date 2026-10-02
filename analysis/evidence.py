#!/usr/bin/env python3
"""Strict quic-12 JSON-SEQ reader, correlation and local standalone evidence viewer."""
import csv,html,json,math,sys
from collections import Counter,defaultdict
from pathlib import Path
from validate import require,validate
SCHEMA='urn:ietf:params:qlog:events:quic-12'
PROGRESS=['schema_version','experiment_id','run_id','resource_id','attempt_index','elapsed_ms','payload_bytes_received']

def read_qlog(path):
 require(Path(path).stat().st_size<=64*1024*1024,'qlog exceeds 64MiB reader bound')
 raw=Path(path).read_bytes()
 require(raw.startswith(b'\x1e'),'qlog must be JSON-SEQ; renaming is not conversion')
 parts=raw.split(b'\x1e')[1:]
 require(all(p.strip() for p in parts),'empty qlog record')
 records=[json.loads(p) for p in parts]
 require(len(records)>1,'qlog has no events')
 header,*events=records
 require(header['file_schema']=='urn:ietf:params:qlog:file:sequential' and header['serialization_format']=='application/qlog+json-seq','wrong qlog serialization')
 require(header['trace']['event_schemas']==[SCHEMA],'unsupported qlog event schema')
 last=-1
 for e in events:
  require(type(e['time']) in (int,float) and math.isfinite(e['time']) and e['time']>=0,'qlog time invalid')
  last=e['time'];require(isinstance(e['name'],str) and isinstance(e['data'],dict),'qlog event invalid')
 return header,events

def correlated(client_dir,server_dir,rid):
 cm=json.loads((Path(client_dir)/'mapping.json').read_text());sm=json.loads((Path(server_dir)/'mapping.json').read_text())
 pairs=[]
 require(cm['event_schema']==sm['event_schema']==SCHEMA,'mapping schema differs')
 for c in cm['connections']:
  require(c['run_id']==rid and c['perspective']=='client' and c['role'] in ('ticket','target'),'client mapping mismatch')
  candidates=[s for s in sm['connections'] if s['odcid']==c['odcid'] and s['perspective']=='server']
  require(len(candidates)==1,'server connection not uniquely mapped by ODCID')
  s=candidates[0]
  require(Path(c['path']).name==c['path'] and Path(s['path']).name==s['path'],'unsafe mapping path')
  ch,ce=read_qlog(Path(client_dir)/c['path']);sh,se=read_qlog(Path(server_dir)/s['path'])
  for m,h in ((c,ch),(s,sh)):
   require(h['trace']['common_fields']['group_id']==m['odcid'] and h['trace']['vantage_point']['type']==m['perspective'],'trace identity differs')
  cc=next(e['data'] for e in ce if e['name']=='transport:connection_started');sc=next(e['data'] for e in se if e['name']=='transport:connection_started')
  require(cc['local']['port_v4']==sc['remote']['port_v4'] and cc['remote']['port_v4']==sc['local']['port_v4'],'trace endpoint ports differ')
  # Resolve wildcard bound address using server-observed remote. Ports plus
  # shared ODCID corroborate; filename order is never used for correlation.
  require(cc['remote']['ip_v4']==sc['local']['ip_v4'],'trace peer addresses differ')
  pairs.append(dict(run_id=rid,role=c['role'],odcid=c['odcid'],client_file=c['path'],server_file=s['path'],client_endpoint=sc['remote'],server_endpoint=sc['local'],client_header=ch,server_header=sh,client_events=ce,server_events=se))
 require(len({p['odcid'] for p in pairs})==len(pairs),'duplicate trace identity')
 return pairs

def check_progress(out):
 out=Path(out);validate(out)
 raw_files=list((out/'raw').glob('*.json'));require(len(raw_files)==1,'one evidence trial required')
 record=json.loads(raw_files[0].read_text());run=record['run'];streams={s['resource_id']:s for s in record['streams']}
 with (out/'progress.csv').open(newline='') as f:
  reader=csv.DictReader(f);require(reader.fieldnames==PROGRESS,'progress header differs');rows=list(reader)
 previous={};last={}
 for row in rows:
  key=(int(row['resource_id']),int(row['attempt_index']));t=float(row['elapsed_ms']);b=int(row['payload_bytes_received']);s=streams[key[0]]
  require(row['schema_version']=='1' and row['run_id']==run['run_id'] and row['experiment_id']==run['experiment_id'],'progress FK mismatch')
  require(0<=key[1]<=run['fallback_count'] and math.isfinite(t) and 0<=t<=run['elapsed_ms']+1,'progress attempt/time invalid')
  pt,pb=previous.get(key,(-1,0));require(t>=pt and pb<b<=s['bytes_expected'],'progress nonmonotonic/overflow')
  require(b%16384==0 or b==s['bytes_expected'],'progress threshold differs')
  previous[key]=(t,b);last[key]=b
 for s in streams.values():
  if s['success']:require(last.get((s['resource_id'],s['attempt_index']))==s['bytes_received'],'successful resource progress incomplete')
 return record,rows

def early_qlog(pairs,record):
 target=next(p for p in pairs if p['role']=='target');run=record['run']
 by_id={s['transport_stream_id']:s['resource_id'] for s in record['streams']}
 sent=[];received=[]
 for perspective,evs,out in [('client',target['client_events'],sent),('server',target['server_events'],received)]:
  event='transport:packet_sent' if perspective=='client' else 'transport:packet_received'
  for e in evs:
   d=e['data'];h=d.get('header',{})
   if e['name']!=event or h.get('packet_type')!='0RTT':continue
   for f in d.get('frames',[]):
    if f['frame_type']=='stream' and f['stream_id'] in by_id and f['offset']==0 and f['length']>=32:
     out.append(dict(packet_number=h['packet_number'],stream_id=f['stream_id'],resource_id=by_id[f['stream_id']],offset=f['offset'],length=f['length'],qlog_time_ms=e['time']))
 api=run['success'] and run['tls_resumed'] is True and run['used_0rtt'] is True and run['attempted_0rtt'] is True and run['early_rejected'] is False and run['fallback_count']==0 and all(s['request_end_ms']<run['handshake_ms'] for s in record['streams'])
 matched=[s for s in sent if any(r['packet_number']==s['packet_number'] and r['stream_id']==s['stream_id'] for r in received)]
 return dict(status='PASS' if api and len({s['resource_id'] for s in matched})==len(by_id) else 'INCONCLUSIVE',api_qualified=api,sent=sent,received=received,matched=matched,limitation='qlog identifies STREAM range, not encrypted payload content; decrypted PCAP REQUEST required for full proof')

def viewer(path,pairs,rows,rid):
 # A standalone local viewer for the actual quic-12 schema. No public upload.
 data=dict(run_id=rid,traces=[dict(label=p['role']+'/'+side,odcid=p['odcid'],events=p[side+'_events']) for p in pairs for side in ('client','server')],progress=rows)
 payload=json.dumps(data,allow_nan=False).replace('<','\\u003c')
 page='''<!doctype html><meta charset="utf-8"><title>QUIC lab evidence</title><style>body{font:16px system-ui;max-width:1300px;margin:24px auto;padding:0 20px;background:#fafafa;color:#18232d}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:7px;border-bottom:1px solid #ddd;text-align:left}pre{white-space:pre-wrap}svg{background:white;border:1px solid #ccc;width:100%}select,input{font:inherit;padding:5px}details{margin:14px 0}</style><h1></h1><p>Local viewer · JSON-SEQ · quic-12. Time is relative to each trace. Client progress uses its own t0; cross-process latency is not computed. Progress samples follow validated DATA frames at 16 KiB thresholds.</p><label>Trace <select id="trace"></select></label> <label>Event filter <input id="filter" placeholder="packet / lost / stream / metrics"></label><p id="counts"></p><h2>Client payload progress (ms / MiB)</h2><svg id="plot" viewBox="0 0 1000 260"></svg><h2>Events</h2><table><thead><tr><th>Time (ms)</th><th>Event</th><th>Packet / frames / details</th></tr></thead><tbody></tbody></table><script>const D=__DATA__;document.querySelector('h1').textContent=D.run_id;const T=document.querySelector('#trace'),F=document.querySelector('#filter');for(const t of D.traces){const o=document.createElement('option');o.textContent=t.label+' · '+t.odcid;T.add(o)}function render(){const t=D.traces[T.selectedIndex]??{events:[]},ev=t.events.filter(e=>(e.name+JSON.stringify(e.data)).includes(F.value));document.querySelector('#counts').textContent=ev.length+' / '+t.events.length+' events';const b=document.querySelector('tbody');b.replaceChildren();for(const e of ev){const tr=document.createElement('tr');for(const v of [e.time.toFixed(3),e.name,JSON.stringify(e.data)]){const td=document.createElement('td');td.textContent=v;tr.append(td)}b.append(tr)}}T.onchange=F.oninput=render;render();const S=document.querySelector('#plot'),ns='http://www.w3.org/2000/svg',groups={};for(const r of D.progress){(groups[r.resource_id+'/'+r.attempt_index]??=[]).push(r)}const maxT=Math.max(1,...D.progress.map(r=>+r.elapsed_ms)),maxB=Math.max(1,...D.progress.map(r=>+r.payload_bytes_received));let i=0;for(const [k,rs] of Object.entries(groups)){const l=document.createElementNS(ns,'polyline');l.setAttribute('points',rs.map(r=>[55+900*(+r.elapsed_ms)/maxT,225-190*(+r.payload_bytes_received)/maxB].join(',')).join(' '));l.setAttribute('fill','none');l.setAttribute('stroke',`hsl(${i*57},65%,40%)`);S.append(l);const text=document.createElementNS(ns,'text');text.setAttribute('x',65+i*135);text.setAttribute('y',20);text.textContent='resource/attempt '+k;S.append(text);i++}for(const [x,y,v] of [[55,250,'0 ms'],[800,250,maxT.toFixed(2)+' ms'],[2,225,'0'],[2,40,(maxB/1048576).toFixed(2)+' MiB']]){const t=document.createElementNS(ns,'text');t.setAttribute('x',x);t.setAttribute('y',y);t.textContent=v;S.append(t)}</script>'''
 Path(path).write_text(page.replace('__DATA__',payload))
 return dict(path=str(path),trace_count=len(data['traces']),events=sum(len(t['events']) for t in data['traces']),progress_points=len(rows),schema=SCHEMA,offline=True)

def render_timeline(path,pairs,rows,rid):
 # Raster + SVG provide an offline viewer that can actually be opened in WSL
 # without qvis schema assumptions or a browser installation.
 import os
 repo=Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(repo/'.tools/analysis'));os.environ.setdefault('MPLCONFIGDIR',str(repo/'.tools/matplotlib'))
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(2,1,figsize=(12,7),layout='constrained')
 for p in pairs:
  if p['role']!='target':continue
  for side in ('client','server'):
   es=p[side+'_events']
   for name,marker in [('transport:packet_sent','>'),('transport:packet_received','<'),('recovery:packet_lost','x')]:
    ts=[e['time'] for e in es if e['name']==name]
    axes[0].scatter(ts,[side+'/'+name]*len(ts),s=9,marker=marker)
 axes[0].set_xlabel('ms from each qlog reference (separate clocks)');axes[0].set_title(rid+' · quic-12 packet/receive/loss events')
 grouped=defaultdict(list)
 for r in rows:grouped[(r['resource_id'],r['attempt_index'])].append(r)
 for (resource,attempt),values in grouped.items():
  axes[1].step([float(r['elapsed_ms']) for r in values],[int(r['payload_bytes_received'])/1048576 for r in values],where='post',label=f'resource {resource}, attempt {attempt}')
 axes[1].set_xlabel('ms from client t0');axes[1].set_ylabel('payload MiB');
 if grouped:axes[1].legend(ncol=3)
 axes[1].grid(alpha=.2)
 fig.suptitle('Evidence instrumentation · validated DATA at 16 KiB thresholds · timeline alone does not prove HOL',fontsize=10)
 path=Path(path);fig.savefig(path,dpi=130);fig.savefig(path.with_suffix('.svg'));plt.close(fig)
