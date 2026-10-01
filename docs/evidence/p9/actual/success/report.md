# P9 CSV-derived results

Experiment: `bulk_20261001T040343_aba00c8f14659393`; execution: `loopback-test`.

All scheduled rows: 6; success 6; failed 0; measured 4; excluded warmups 2.

Latency/goodput summarize successful measured trials. Failures remain in every denominator. p95 is nearest-rank; sample stddev is null below two observations. No outliers removed.

| Scenario | Transport | Metric | Attempted | Success | Failed | Median | p95 |
|---|---|---|---:|---:|---:|---:|---:|
| loopback-test | quic | total_ms | 2 | 2 | 0 | 79.134 | 116.209 |
| loopback-test | quic | ttfa_ms | 2 | 2 | 0 | 5.229 | 6.419 |
| loopback-test | quic | goodput_mbps | 2 | 2 | 0 | 874.975 | 1294.623 |
| loopback-test | tcp | total_ms | 2 | 2 | 0 | 26.596 | 29.988 |
| loopback-test | tcp | ttfa_ms | 2 | 2 | 0 | 1.742 | 1.792 |
| loopback-test | tcp | goodput_mbps | 2 | 2 | 0 | 2045.513 | 2317.429 |

Artifacts: runs.csv, streams.csv, raw/, schedule.json, manifest.json, merge.json, summary.csv, resource-summary.csv and plots/.

Limitations: shared WSL2 host/kernel/CPU, different kernel/userspace transport and scheduling, differing packetization/congestion control; paired seed does not imply identical lost application bytes. Configured loss affects downstream control/ACK traffic too; qdisc drops can include overflow. Small cohorts/p95 describe this testbed and workload. Performance plots do not establish HOL causation. P10 resumption/early and P11 qlog/PCAP/progress evidence remain pending.
