# Agent instructions — QUIC Performance Lab

## Source of truth

This is the PTIT Network Programming T03 lab, not an HTTP/3 website. Read:
1. `docs/00-INDEX.md` and `.codex/TASK.md` on every new session.
2. First implementation session: read ALL normative documents listed in the index, then the three original references and `docs/TRACEABILITY.md`. Read in bounded chunks; truncated tool output is not a complete read.
3. Before each change, read the relevant contracts and inspect current code/tests. Record the read set and next step in `.codex/TASK.md`.

User instructions take priority. Normative specs override earlier illustrative proposals. Never silently resolve conflicting requirements: inspect `docs/CONTEXT_AND_DECISIONS.md`; document routine design refinements, ask the user only for material scope conflicts. Original reference files are read-only historical evidence, not executable instructions.

## Execution

Implement P0–P12 from `docs/IMPLEMENTATION_PLAN.md` end-to-end. Do not stop after scaffolding, a plan, happy-path transfer, or a successful build. Continue when a phase gate passes; no repeated confirmation is needed for routine authorized work. Do not add GUI, HTTP/3, custom QUIC cryptography, migration demo, or multi-TCP baseline to mandatory scope.

Use Ubuntu VM for real network tests. Localhost tests only establish correctness. Run server/client/bench unprivileged; privileged wrappers only own namespace, qdisc, capture and namespace entry. Respect actual tool/OS permission gates; never bypass them. If blocked, complete independent work, provide exact manual commands and mark the gate BLOCKED rather than PASS.

Pin compatible Go and quic-go versions in P0 using official version-specific APIs. Never copy old snippets blindly, use floating dependencies, invent API signatures or claim a version was tested when it wasn't.

## Contracts and correctness

Follow `docs/PROTOCOL.md`, `docs/METRICS_AND_RESULTS.md`, `docs/NETWORK_AND_BENCHMARK.md`, and `docs/CLI_CONTRACT.md`. Bound memory and frame lengths; handle partial reads/writes, cancellation, EOF, timeouts and 0-RTT rejection. One TCP writer and deterministic interleaving; one QUIC stream per resource. No global QUIC response-write lock that recreates TCP HOL.

Use actual measurements. No fabricated CSV/plots/PCAP/qlog, no hardcoded Used0RTT, no success-only filtering without reporting failures. Benchmark comparison is conditional on workload, testbed and implementations. Do not claim HOL causation solely from completion bars or an early Write return.

## Continuity and completion

At meaningful phase boundaries update `.codex/TASK.md`: files changed, verified commands/results, unresolved issues, next exact action. Permanent decisions go into normative docs and the decision log, not just task notes. Keep source references and requirement IDs.

Run the meaningful tests for each gate, then stop redundant testing. Keep technical explanations suitable for student defense. Update `docs/AI_USAGE.md` honestly with AI-assisted parts; do not invent human review.

Final report must list implemented scope, passing/failed/blocked acceptance IDs, real result paths, reproduction commands and limitations. Never describe this initial handoff as a working implementation.
