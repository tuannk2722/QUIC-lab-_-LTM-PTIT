#!/usr/bin/env python3
"""Use Wireshark for cryptography/QUIC decoding; only interpret its PDML here."""
import json,struct,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from validate import require
REPO=Path(__file__).resolve().parents[1]

def fields(node,name):return [f for f in node.iter('field') if f.get('name')==name]
def show(node,name,default=None):
 fs=fields(node,name);return fs[0].get('show',fs[0].get('value')) if fs else default

def parse_pdml(path):
 packets=[]
 for _,packet in ET.iterparse(path,events=('end',)):
  if packet.tag!='packet':continue
  base=dict(frame_number=int(show(packet,'frame.number')),epoch=float(show(packet,'frame.time_epoch')),src=show(packet,'ip.src'),dst=show(packet,'ip.dst'))
  udp=next((p for p in packet if p.get('name')=='udp'),None)
  if udp is not None:
   base.update(protocol='udp',srcport=int(show(udp,'udp.srcport')),dstport=int(show(udp,'udp.dstport')))
   for proto in [p for p in packet if p.get('name')=='quic']:
    types=fields(proto,'quic.long.packet_type');pns=fields(proto,'quic.packet_number')
    # A coalesced protocol tree with multiple headers is ambiguous for this
    # reader: never attach a 1RTT request to a sibling 0RTT header.
    row=dict(base,quic=True,packet_type=int(types[0].get('show')) if len(types)==1 else None,packet_number=int(pns[0].get('show')) if len(pns)==1 else None,streams=[],ambiguous_header=len(types)>1 or len(pns)>1)
    for tree in fields(proto,'quic.frame'):
     ids=fields(tree,'quic.stream.stream_id');data=fields(tree,'quic.stream_data')
     if len(ids)==1 and len(data)==1:
      blob=data[0].get('value',data[0].get('show','')).replace(':','')
      row['streams'].append(dict(stream_id=int(ids[0].get('show')),offset=int(show(tree,'quic.stream.offset','0')),length=int(show(tree,'quic.stream.length',str(len(blob)//2))),data_hex=blob))
    packets.append(row)
  tcp=next((p for p in packet if p.get('name')=='tcp'),None)
  if tcp is not None:
   packets.append(dict(base,protocol='tcp',srcport=int(show(tcp,'tcp.srcport')),dstport=int(show(tcp,'tcp.dstport')),seq=int(show(tcp,'tcp.seq_raw')),ack=int(show(tcp,'tcp.ack_raw')),length=int(show(tcp,'tcp.len')),sack_left=[int(f.get('show')) for f in fields(tcp,'tcp.options.sack_le')],sack_right=[int(f.get('show')) for f in fields(tcp,'tcp.options.sack_re')]))
  packet.clear()
 return packets

def decode(pcap,keylog,out):
 out=Path(out);out.mkdir(exist_ok=True)
 pdml=out/'packets.pdml';log=out/'decode.log'
 cmd=['bash',str(REPO/'scripts/tshark.sh'),'-n','-2','-r',str(pcap),'-d','udp.port==4433,quic','-o','tls.keylog_file:'+str(keylog),'-o','tcp.relative_sequence_numbers:FALSE','-T','pdml']
 with pdml.open('wb') as f,log.open('wb') as e:subprocess.run(cmd,stdout=f,stderr=e,check=True,timeout=90)
 packets=parse_pdml(pdml)
 (out/'packets.json').write_text(json.dumps(packets,indent=2)+'\n')
 (out/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
 return packets

def request_bytes(data,rid,count,chunk):
 raw=bytes.fromhex(data)
 if len(raw)<32:return False
 magic,typ,flags,reserved,resource,offset,length=struct.unpack('!4sBBHIQI',raw[:24])
 return (magic,typ,flags,reserved,resource,offset,length)==(b'QB01',1,0,0,rid,0,8) and struct.unpack('!II',raw[24:32])==(count,chunk)

def early_packet_proof(packets,pair,record,api_qlog):
 r=record['run'];proof=[];client=pair['client_endpoint'];server=pair['server_endpoint']
 for p in packets:
  if p.get('protocol')!='udp' or p.get('ambiguous_header') or p.get('packet_type')!=1 or p.get('packet_number') is None:continue
  if (p['src'],p['srcport'],p['dst'],p['dstport'])!=(client['ip_v4'],client['port_v4'],server['ip_v4'],server['port_v4']):continue
  for f in p['streams']:
   s=next((s for s in record['streams'] if s['transport_stream_id']==f['stream_id']),None)
   if s and f['offset']==0 and request_bytes(f['data_hex'],s['resource_id'],r['resource_count'],r['chunk_bytes']):
    if any(q['packet_number']==p['packet_number'] and q['stream_id']==f['stream_id'] for q in api_qlog['matched']):
     proof.append(dict(frame_number=p['frame_number'],packet_number=p['packet_number'],stream_id=f['stream_id'],resource_id=s['resource_id'],qb01_request_hex=f['data_hex'][:64],source_port=p['srcport'],destination_port=p['dstport']))
 return dict(status='PASS' if api_qlog['status']=='PASS' and len({p['resource_id'] for p in proof})==r['resource_count'] else 'INCONCLUSIVE',requests=proof,criterion='decrypted client 0RTT packet contains QB01 REQUEST; PN/native stream mapped to server-received qlog and actual API state')
