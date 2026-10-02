#!/usr/bin/env python3
"""Conservative causal candidates. No completion-bar or write-enqueue proof."""
from datetime import datetime

def epoch(value):return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
def progress_clock(record,rows):
 t0=epoch(record['run']['timestamp_utc'])
 return [(t0+float(r['elapsed_ms'])/1000,int(r['resource_id']),int(r['payload_bytes_received'])) for r in rows]

def tcp_candidate(packets,record,rows):
 points=progress_clock(record,rows)
 # Use receiver-generated cumulative ACK + SACK, which reports data actually
 # present beyond the kernel gap even when eth0 capture is before IFB loss.
 for i,p in enumerate(packets):
  if p.get('protocol')!='tcp' or p['dstport']!=4433 or p.get('capture_namespace')!='qclient':continue
  edges=[(a,b) for a,b in zip(p['sack_left'],p['sack_right']) if b>a>p['ack']]
  if not edges:continue
  gap=p['ack'];end=max(b for a,b in edges)
  filled=next((a for a in packets[i+1:] if a.get('protocol')=='tcp' and a.get('capture_namespace')=='qclient' and a['dstport']==4433 and a['ack']>=end),None)
  if filled is None:continue
  # Retransmission of the byte containing the gap from the sender, after SACK.
  tx=[a for a in packets if a.get('protocol')=='tcp' and a.get('capture_namespace')=='qserver' and a['srcport']==4433 and a['seq']<=gap<a['seq']+a['length'] and a['epoch']<=filled['epoch']]
  original=[a for a in tx if a['epoch']<p['epoch']];retry=[a for a in tx if a['epoch']>=p['epoch']]
  after_gap=[a for a in packets if a.get('protocol')=='tcp' and a.get('capture_namespace')=='qserver' and a['srcport']==4433 and gap<a['seq']<end and a['epoch']<=p['epoch']]
  if not original or not retry or not after_gap:continue
  left=p['epoch']+.003;right=filled['epoch']-.003
  if right-left<.010:continue
  stalled=not any(left<t<right for t,_,_ in points)
  before=any(t<p['epoch'] for t,_,_ in points);after=any(t>filled['epoch'] for t,_,_ in points)
  if stalled and before and after:
   return dict(status='PASS',gap_seq_raw=gap,sack_edges=edges,ack_frame=p['frame_number'],advancing_ack_frame=filled['frame_number'],original_frame=original[0]['frame_number'],retry_frame=retry[0]['frame_number'],later_byte_frames=[a['frame_number'] for a in after_gap[:8]],stall_epoch=[left,right],resolution='16KiB validated DATA; 3ms margin; no claim about which resource lost its encrypted TLS bytes')
 return dict(status='INCONCLUSIVE',reason='no cumulative ACK/SACK byte gap with retransmission and matching app stall at this sampling resolution')

def quic_candidate(pair,record,rows):
 events=pair['client_events'];server=pair['server_events'];points=progress_clock(record,rows)
 reference=epoch(pair['client_header']['trace']['common_fields']['reference_time']['wall_clock_time'])
 resource={s['transport_stream_id']:s['resource_id'] for s in record['streams']}
 lost={e['data']['header']['packet_number'] for e in server if e['name']=='recovery:packet_lost' and e['data']['header']['packet_type']=='1RTT'}
 lost_frames={}
 for e in server:
  d=e['data'];h=d.get('header',{})
  if e['name']=='transport:packet_sent' and h.get('packet_type')=='1RTT' and h['packet_number'] in lost:
   lost_frames[h['packet_number']]=[f for f in d.get('frames',[]) if f['frame_type']=='stream' and f['length']>0]
 received=sorted([e for e in events if e['name']=='transport:packet_received' and e['data']['header']['packet_type']=='1RTT'],key=lambda e:e['time'])
 received_pns={e['data']['header']['packet_number'] for e in received}
 coverage={sid:[] for sid in resource}
 def contiguous(ranges):
  end=0
  for a,b in sorted(ranges):
   if a>end:break
   end=max(end,b)
  return end
 for i,e in enumerate(received):
  pn=e['data']['header']['packet_number']
  for f in e['data'].get('frames',[]):
   if f['frame_type']!='stream' or f['stream_id'] not in resource or f['length']<=0:continue
   sid=f['stream_id'];gap=contiguous(coverage[sid]);off=f['offset'];length=f['length']
   if off>gap:
    sources=[(lp,lf) for lp,fs in lost_frames.items() if lp not in received_pns for lf in fs if lf['stream_id']==sid and lf['offset']<=gap<lf['offset']+lf['length']]
    later_coverage=list(coverage[sid])+[(off,off+length)];fill=None
    for after in received[i+1:]:
     for g in after['data'].get('frames',[]):
      if g['frame_type']=='stream' and g['stream_id']==sid:later_coverage.append((g['offset'],g['offset']+g['length']))
     if contiguous(later_coverage)>=off+length:fill=after;break
    if sources and fill:
     left=reference+e['time']/1000+.003;right=reference+fill['time']/1000-.003
     affected=resource[sid];siblings=[(t,r,b) for t,r,b in points if r!=affected and left<t<right]
     own=[t for t,r,b in points if r==affected and left<t<right]
     affected_packet_streams={f['stream_id'] for f in lost_frames[sources[0][0]]}
     independent=[p for p in siblings if next(s for s,r in resource.items() if r==p[1]) not in affected_packet_streams]
     if right-left>=.010 and independent and not own and any(t>right and r==affected for t,r,b in points):
      return dict(status='PASS',lost_packet_number=sources[0][0],lost_packet_stream_ranges=lost_frames[sources[0][0]],stream_id=sid,resource_id=affected,gap_offset=gap,later_offset=off,later_packet_number=pn,recovery_packet_number=fill['data']['header']['packet_number'],gap_epoch=[left,right],sibling_progress=independent[:8],criterion='server lost packet; client stream gap/out-of-order later bytes; distinct sibling delivers payload before gap recovery in a new PN; affected stream resumes',caveat='packet may contain several streams; flow/congestion remain shared; wall-clock alignment same host, 3ms margin')
   coverage[sid].append((off,off+length))
 return dict(status='INCONCLUSIVE',reason='no loss/range/receive/progress interval correlates independent sibling delivery with a blocked stream and later recovery')
