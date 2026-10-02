import copy,json,struct,tempfile,unittest
from pathlib import Path
from evidence import read_qlog
from packet_evidence import request_bytes,early_packet_proof,parse_pdml
from hol import tcp_candidate,quic_candidate
class EvidenceTests(unittest.TestCase):
 def test_qlog_wrong_schema_truncation_and_nonmonotonic(self):
  header={'file_schema':'urn:ietf:params:qlog:file:sequential','serialization_format':'application/qlog+json-seq','trace':{'event_schemas':['urn:ietf:params:qlog:events:quic-12']}}
  events=[{'time':1,'name':'a','data':{}},{'time':.5,'name':'b','data':{}}] # Concurrent producers may enqueue out of time order.
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'trace.sqlog';data=''.join('\x1e'+json.dumps(r)+'\n' for r in [header,*events]);p.write_text(data)
   self.assertEqual(len(read_qlog(p)[1]),2)
   p.write_text(data+'\x1e{');self.assertRaises(ValueError,read_qlog,p)
   header['trace']['event_schemas']=['old'];p.write_text('\x1e'+json.dumps(header)+'\x1e'+json.dumps(events[0]));self.assertRaises(ValueError,read_qlog,p)
 def test_early_proof_requires_same_packet_payload_and_native_stream(self):
  blob=(struct.pack('!4sBBHIQI',b'QB01',1,0,0,1,0,8)+struct.pack('!II',1,1024)).hex()
  self.assertTrue(request_bytes(blob,1,1,1024));self.assertFalse(request_bytes(blob,2,1,1024))
  pair={'client_endpoint':{'ip_v4':'10.10.0.1','port_v4':12345},'server_endpoint':{'ip_v4':'10.10.0.2','port_v4':4433}}
  record={'run':{'resource_count':1,'chunk_bytes':1024},'streams':[{'resource_id':1,'transport_stream_id':0}]}
  packet={'protocol':'udp','src':'10.10.0.1','dst':'10.10.0.2','srcport':12345,'dstport':4433,'ambiguous_header':False,'packet_type':1,'packet_number':7,'frame_number':20,'streams':[{'stream_id':0,'offset':0,'data_hex':blob}]}
  qlog={'status':'PASS','matched':[{'packet_number':7,'stream_id':0}]}
  self.assertEqual(early_packet_proof([packet],pair,record,qlog)['status'],'PASS')
  for key,value in [('ambiguous_header',True),('packet_type',None),('srcport',54321),('packet_number',8)]:
   changed=copy.deepcopy(packet);changed[key]=value;self.assertEqual(early_packet_proof([changed],pair,record,qlog)['status'],'INCONCLUSIVE')
  changed=copy.deepcopy(packet);changed['streams'][0]['data_hex']='00'*32
  self.assertEqual(early_packet_proof([changed],pair,record,qlog)['status'],'INCONCLUSIVE')
 def test_completion_or_loss_alone_cannot_prove_hol(self):
  record={'run':{'timestamp_utc':'2026-10-02T00:00:00Z'}}
  self.assertEqual(tcp_candidate([],record,[])['status'],'INCONCLUSIVE')
  pair={'client_events':[],'server_events':[{'name':'recovery:packet_lost','data':{'header':{'packet_type':'1RTT','packet_number':1}}}], 'client_header':{'trace':{'common_fields':{'reference_time':{'wall_clock_time':'2026-10-02T00:00:00Z'}}}}}
  record['streams']=[{'transport_stream_id':0,'resource_id':1}]
  self.assertEqual(quic_candidate(pair,record,[])['status'],'INCONCLUSIVE')
 def test_pdml_coalesced_headers_are_never_associated(self):
  # This is a schema unit fixture, never measured/capture evidence.
  xml='''<pdml><packet><proto name="frame"><field name="frame.number" show="1"/><field name="frame.time_epoch" show="1.0"/></proto><proto name="ip"><field name="ip.src" show="10.10.0.1"/><field name="ip.dst" show="10.10.0.2"/></proto><proto name="udp"><field name="udp.srcport" show="12345"/><field name="udp.dstport" show="4433"/></proto><proto name="quic"><field name="quic.long.packet_type" show="0"/><field name="quic.long.packet_type" show="1"/><field name="quic.packet_number" show="0"/><field name="quic.packet_number" show="1"/></proto></packet></pdml>'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'unit.pdml';p.write_text(xml);packets=parse_pdml(p)
   self.assertTrue(packets[0]['ambiguous_header']);self.assertIsNone(packets[0]['packet_type'])
 def test_tcp_sack_requires_sender_retry_and_app_stall(self):
  from hol import epoch
  origin=epoch('2026-10-02T00:00:00Z')
  def packet(t,ns,seq,length,ack=0,left=[],right=[]):
   return dict(protocol='tcp',epoch=origin+t,capture_namespace=ns,srcport=4433 if ns=='qserver' else 12345,dstport=12345 if ns=='qserver' else 4433,seq=seq,length=length,ack=ack,sack_left=left,sack_right=right,frame_number=round(t*1000))
  ps=[packet(.01,'qserver',100,100),packet(.02,'qserver',200,100),packet(.03,'qclient',0,0,100,[200],[300]),packet(.07,'qserver',100,100),packet(.10,'qclient',0,0,300)]
  record={'run':{'timestamp_utc':'2026-10-02T00:00:00Z'}}
  rows=[dict(elapsed_ms=t,resource_id=1,payload_bytes_received=b) for t,b in [(15,16384),(115,32768)]]
  self.assertEqual(tcp_candidate(ps,record,rows)['status'],'PASS')
  self.assertEqual(tcp_candidate(ps[:3]+ps[4:],record,rows)['status'],'INCONCLUSIVE')
  self.assertEqual(tcp_candidate(ps,record,rows+[dict(elapsed_ms=60,resource_id=2,payload_bytes_received=16384)])['status'],'INCONCLUSIVE')
 def test_quic_gap_requires_independent_sibling_and_new_packet(self):
  def event(name,pn,t,frames=[]):return dict(name=name,time=t,data={'header':{'packet_type':'1RTT','packet_number':pn},'frames':frames})
  def stream(sid,off):return dict(frame_type='stream',stream_id=sid,offset=off,length=10)
  pair={'client_events':[event('transport:packet_received',2,20,[stream(0,10)]),event('transport:packet_received',3,100,[stream(0,0)])], 'server_events':[event('transport:packet_sent',1,1,[stream(0,0)]),event('recovery:packet_lost',1,50)], 'client_header':{'trace':{'common_fields':{'reference_time':{'wall_clock_time':'2026-10-02T00:00:00Z'}}}}}
  record={'run':{'timestamp_utc':'2026-10-02T00:00:00Z'},'streams':[{'transport_stream_id':0,'resource_id':1},{'transport_stream_id':4,'resource_id':2}]}
  rows=[dict(elapsed_ms=40,resource_id=2,payload_bytes_received=16384),dict(elapsed_ms=105,resource_id=1,payload_bytes_received=16384)]
  self.assertEqual(quic_candidate(pair,record,rows)['status'],'PASS')
  shared=copy.deepcopy(pair);shared['server_events'][0]['data']['frames'].append(stream(4,0))
  self.assertEqual(quic_candidate(shared,record,rows)['status'],'INCONCLUSIVE')
  spurious=copy.deepcopy(pair);spurious['client_events'].insert(0,event('transport:packet_received',1,10,[stream(0,0)]))
  self.assertEqual(quic_candidate(spurious,record,rows)['status'],'INCONCLUSIVE')
if __name__=='__main__':unittest.main()
