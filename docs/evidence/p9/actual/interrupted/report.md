# P9 CSV-derived results

Experiment: `bulk_20261001T040344_ef7dd5f26aa35ec1`; execution: `loopback-test`.

All scheduled rows: 4; success 1; failed 3; measured 4; excluded warmups 0.

Latency/goodput summarize successful measured trials. Failures remain in every denominator. p95 is nearest-rank; sample stddev is null below two observations. No outliers removed.

| Scenario | Transport | Metric | Attempted | Success | Failed | Median | p95 |
|---|---|---|---:|---:|---:|---:|---:|
| loopback-test | quic | total_ms | 2 | 0 | 2 | — | — |
| loopback-test | quic | ttfa_ms | 2 | 0 | 2 | — | — |
| loopback-test | quic | goodput_mbps | 2 | 0 | 2 | — | — |
| loopback-test | tcp | total_ms | 2 | 1 | 1 | 16.667 | 16.667 |
| loopback-test | tcp | ttfa_ms | 2 | 1 | 1 | 1.684 | 1.684 |
| loopback-test | tcp | goodput_mbps | 2 | 1 | 1 | 3293.382 | 3293.382 |

Artifacts: runs.csv, streams.csv, raw/, schedule.json, manifest.json, merge.json, summary.csv, resource-summary.csv and plots/.

Limitations: shared WSL2 host/kernel/CPU, different kernel/userspace transport and scheduling, differing packetization/congestion control; paired seed does not imply identical lost application bytes. Configured loss affects downstream control/ACK traffic too; qdisc drops can include overflow. Small cohorts/p95 describe this testbed and workload. Performance plots do not establish HOL causation. P10 resumption/early and P11 qlog/PCAP/progress evidence remain pending.
