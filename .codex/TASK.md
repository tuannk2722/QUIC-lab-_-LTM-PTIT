# Task checkpoint

Updated: 2026-09-30 UTC
Status: ENVIRONMENT_MIGRATION_COMPLETE / IMPLEMENTATION_NOT_STARTED / AWAITING_HUMAN_REVIEW
Current phase: P0 NOT_STARTED / G00 NOT_RUN
Next exact action: human review of this documentation migration; only after explicit user authorization, begin P0 alone using AGENTS/INDEX/TASK and the P0 read set in IMPLEMENTATION_PLAN. Do not install/pin Go/quic-go or run later phases before authorization.

## Original handoff — 2026-09-28

- Read 3 attachments.
- Reconciled 31 visible conversation items; user originally chose Ubuntu VM and reported no missing decisions. D13 supersedes only the runtime decision on 2026-09-30.
- Created contracts/config/schema/plan/acceptance/start prompt; no implementation or benchmark.

## Documentation migration — 2026-09-30

- Current environment: Ubuntu under WSL2 on Windows 11; Windows VS Code Remote WSL UI, Linux commands inside WSL2. Machine observations and current repo path are in docs/VERSIONS.md; revalidate during authorized P0.
- User-provided verified capability preflight: netns PASS (qclient/qserver create/remove), veth PASS (create/remove), netem PASS (50 ms qdisc attached), IFB PASS (device created/UP), act_mirred PASS (module loaded); tcpdump available. Agent did not rerun these probes. This is NOT G07/G08 acceptance or a benchmark result.
- D13/D14 permanently record preserved experiment/ingress IFB/mirred and human-gated phases. Run authorized phase gate, update TASK, stop review. Explicit user request is required for automatic multi-phase work.
- No Go/quic-go installation, pin, build or API testing. No application code, schema/config changes, network mutation, benchmark or commit.

## Read set and initial occurrence classification

Fully read AGENTS.md, docs/00-INDEX.md, this TASK, CODEX_START_PROMPT.md, README.md, START_HERE.md, docs/CONTEXT_AND_DECISIONS.md, docs/NETWORK_AND_BENCHMARK.md, docs/VERSIONS.md, docs/IMPLEMENTATION_PLAN.md, docs/ACCEPTANCE.md, docs/METRICS_AND_RESULTS.md, docs/DEMO_SCRIPT.md, docs/TRACEABILITY.md and docs/AI_USAGE.md. Truncated combined output was reread in bounded calls. Also read docs/HANDOFF_VALIDATION.md and schemas/README.md; searched schema environment/manifest fields (no manifest schema in current result-record schema).

Before editing, initial environment hits were classified by semantic location:

- Current normative, update: AGENTS execution; NETWORK§1 (old VM and rejected WSL2 statements); VERSIONS status/environment row; PLAN P0; ACCEPTANCE network state; METRICS manifest hypervisor requirement.
- Current operational, update: START_HERE step 1; TASK next action; README design/reproduction item 7; CODEX_START_PROMPT environment; DEMO prerequisites. Broader VM/workflow search also found NETWORK shared resources/idle threshold, METRICS artifact description, DEMO topology/fallback, PLAN/start prompt automatic continuation.
- Historical/provenance, retain with superseding notes: START_HERE context; TASK original handoff; CONTEXT original request/environment/unknowns/D03; TRACEABILITY opening/row 3 including discussed WSL2 alternative; AI_USAGE initial handoff. HANDOFF_VALIDATION remains unchanged dated 2026-09-28 evidence. Originals/source manifests untouched.

## Files changed

AGENTS.md, CODEX_START_PROMPT.md, README.md, START_HERE.md, .codex/TASK.md; docs/00-INDEX.md, CONTEXT_AND_DECISIONS.md, NETWORK_AND_BENCHMARK.md, VERSIONS.md, IMPLEMENTATION_PLAN.md, ACCEPTANCE.md, METRICS_AND_RESULTS.md, DEMO_SCRIPT.md, TRACEABILITY.md, AI_USAGE.md.

## Validation and limitations

- Initial git status --short: clean (exit 0). Documentation edits completed; initial TASK write hit read-only sandbox and required scoped escalation.
- Post-edit search covers Ubuntu VM, VMware, WSL2, WSL 2, VM state, hypervisor; actual diff reviewed. Remaining old environment names occur only in historical/provenance text: START_HERE original context, CONTEXT original observations/D03/D13 supersession, TRACEABILITY opening/row 3, AI_USAGE initial handoff, and this original handoff/search audit. None is an obsolete current instruction. Manifest now distinguishes execution layer and optional hypervisor.
- git diff --check PASS (exit 0); git status and git diff --stat reviewed. Only the 15 docs/instruction files listed above changed; config/schema/originals/source manifests unchanged.
- No measured result paths exist; supplied capability observations are recorded in VERSIONS, not locally collected logs. G00–G12 NOT_RUN; no execution gate PASS/FAIL/BLOCKED claimed.
- P0/P5/P6 follow-up: revalidate environment/tool versions and implement manifest metadata per METRICS§5. If a schema change becomes necessary, document/version it then; CSV semantics unchanged here.

## Phase status

P0 NOT_STARTED; P1 NOT_STARTED; P2 NOT_STARTED; P3 NOT_STARTED; P4 NOT_STARTED; P5 NOT_STARTED; P6 NOT_STARTED; P7 NOT_STARTED; P8 NOT_STARTED; P9 NOT_STARTED; P10 NOT_STARTED; P11 NOT_STARTED; P12 NOT_STARTED.

## Each checkpoint

Record authorized phase/gate, files read/changed, commands/exit/results and real evidence paths; unresolved/blocked/inconclusive issues, permanent decisions, next exact action and remaining gates. Never mark intent as completion.
