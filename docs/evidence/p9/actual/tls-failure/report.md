# P9 CSV-derived results

Experiment: `bulk_20261001T040343_ed600486532050f8`; execution: `loopback-test`.

All scheduled rows: 2; success 0; failed 2; measured 2; excluded warmups 0.

Latency/goodput summarize successful measured trials. Failures remain in every denominator. p95 is nearest-rank; sample stddev is null below two observations. No outliers removed.

| Scenario | Transport | Metric | Attempted | Success | Failed | Median | p95 |
|---|---|---|---:|---:|---:|---:|---:|
| loopback-test | quic | total_ms | 1 | 0 | 1 | — | — |
| loopback-test | quic | ttfa_ms | 1 | 0 | 1 | — | — |
| loopback-test | quic | goodput_mbps | 1 | 0 | 1 | — | — |
| loopback-test | tcp | total_ms | 1 | 0 | 1 | — | — |
| loopback-test | tcp | ttfa_ms | 1 | 0 | 1 | — | — |
| loopback-test | tcp | goodput_mbps | 1 | 0 | 1 | — | — |

Artifacts: runs.csv, streams.csv, raw/, schedule.json, manifest.json, merge.json, summary.csv, resource-summary.csv and plots/.

Limitations: shared WSL2 host/kernel/CPU, different kernel/userspace transport and scheduling, differing packetization/congestion control; paired seed does not imply identical lost application bytes. Configured loss affects downstream control/ACK traffic too; qdisc drops can include overflow. Small cohorts/p95 describe this testbed and workload. Performance plots do not establish HOL causation. P10 resumption/early and P11 qlog/PCAP/progress evidence remain pending.
