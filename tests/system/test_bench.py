#!/usr/bin/env python3
"""P9 network/idle checker regression fixtures; synthetic unit data only."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('bench_support', REPO / 'scripts/bench-support.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


class NetworkChecks(unittest.TestCase):
    def fixture(self, root):
        rid = 'unit_trial'
        fields = dict(schema_version=1, verified=True, network_profile='ingress-ifb', scenario='rtt50-loss1', netem_seed=123,
                      config_sha256='a'*64, queue_limit_packets=1000, mtu=1500, delay_each_way_ms=25,
                      loss_downstream_pct=1, loss_upstream_pct=0, rate_mbps=20,
                      client_namespace_id='1:2', server_namespace_id='1:3', seed_status='requested-and-verified')
        before = dict(fields, observation={})
        after = dict(fields, observation={})
        for ns in ('qclient', 'qserver'):
            q = dict(kind='netem', bytes=0, packets=0, drops=0, overlimits=0, backlog=0, qlen=0)
            before['observation'][ns] = {'ifb0': {'qdisc': [q]}, 'filters_text': 'Sent 0 bytes 0 pkt'}
            a = dict(q, bytes=7000000 if ns=='qclient' else 100000, packets=5000 if ns=='qclient' else 500, drops=10 if ns=='qclient' else 0)
            after['observation'][ns] = {'ifb0': {'qdisc': [a]}, 'filters_text': f'Sent {a["bytes"]} bytes {a["packets"]} pkt'}
        (root/'network').mkdir(); (root/'shards'/rid/'raw').mkdir(parents=True)
        def put(path, data): path.write_text(json.dumps(data))
        put(root/'schedule.json', {'entries': [{'run_id':rid,'scenario':'rtt50-loss1','netem_seed':123}],
                                  'scenarios_sha256':'a'*64,'scenarios':{'queue_limit_packets':1000,'mtu':1500,'scenarios':[dict(name='rtt50-loss1',**{k:fields[k] for k in ('delay_each_way_ms','loss_downstream_pct','loss_upstream_pct','rate_mbps')})]}})
        put(root/'network'/f'{rid}.before.json',before)
        put(root/'network'/f'{rid}.after.json',after)
        put(root/'shards'/rid/'raw'/f'{rid}.json',{'run':{'success':True,'bytes_received':6291456,'goodput_mbps':15}})
        return rid,before,after

    def test_matching_and_config_or_counter_change(self):
        for mutation in ('none','seed','profile','reset','rate'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); rid,b,a=self.fixture(root)
                if mutation=='seed': a['netem_seed']=124
                if mutation=='profile': a['network_profile']='egress-demo'
                if mutation=='reset': b['observation']['qclient']['ifb0']['qdisc'][0]['packets']=6000
                if mutation=='rate':
                    path=root/'shards'/rid/'raw'/f'{rid}.json'
                    obj=json.loads(path.read_text());obj['run']['goodput_mbps']=100;path.write_text(json.dumps(obj))
                (root/'network'/f'{rid}.before.json').write_text(json.dumps(b))
                (root/'network'/f'{rid}.after.json').write_text(json.dumps(a))
                if mutation=='none': support.check_network(root,rid)
                else:
                    with self.assertRaises(ValueError): support.check_network(root,rid)
                    self.assertEqual(json.loads((root/'network'/f'{rid}.check.json').read_text())['status'],'FAIL')

    def test_idle_requires_drained_queues_and_quiet_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rid,b,a=self.fixture(root)
            left=root/'network'/f'{rid}.before.json';right=root/'network'/f'{rid}.after.json'
            with self.assertRaises(ValueError): support.idle(left,right)
            right.write_text(json.dumps(b));support.idle(left,right)
            b['observation']['qclient']['ifb0']['qdisc'][0]['qlen']=1
            right.write_text(json.dumps(b))
            with self.assertRaises(ValueError): support.idle(left,right)


if __name__=='__main__':
    unittest.main()
