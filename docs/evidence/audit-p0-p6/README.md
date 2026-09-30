# Audit fixes P0–P6 — 2026-09-30

Scope: six review findings; no P7/network impairment or benchmark claims.

- `make build`: exit 0 (`build.log`).
- `make test`: exit 0 (`suite.log`), including new TCP corrupted-middle-resource and EOF-timeout integration tests, QUIC resolver/EOF regression tests, per-resource records, existing G04/G05 tests.
- `make test-race`: exit 0 (`race.log`), localhost permission granted, UID unprivileged.
- `python3 analysis/test_validate.py docs/evidence/p6/actual`: exit 0 (`validator.log`); copies only, original evidence unchanged.
- `bash docs/evidence/p6/run-g06.sh`: exit 0 (`actual-trials.log`). Actual TCP/QUIC success + TLS failure at `results/p6-g06-mCkEvs/`, copied verbatim to `actual/` here. Each bulk trial has six resource rows; validator and mutation regressions pass.
- Actual QUIC resolve failure and socket-creation failure: client exit 1, validator exit 0, raw/CSV in `resolve_failure/` and `socket_failure/`. Socket failure was the sandbox's real EPERM, not simulated network data. Commands below reproduce the inputs; socket EPERM requires the restricted sandbox.

```sh
make build
make test
make test-race
python3 analysis/test_validate.py docs/evidence/p6/actual
bash docs/evidence/p6/run-g06.sh
bin/client --transport=quic --profile=handshake --addr='[bad::ip]:4433' --out=results/audit-resolve-new --experiment-id=audit --run-id=resolve_failure
python3 analysis/validate.py results/audit-resolve-new
bin/client --transport=quic --profile=handshake --addr=127.0.0.1:4433 --out=results/audit-socket-new --experiment-id=audit --run-id=socket_failure
```

Output directories must be new. Historical `suite-sandbox-blocked.log` records socket restrictions; `suite-before-timeout-fix.log` records the regression detecting cancellation closing a socket before the deadline read error. Final suite/race pass after preserving the context cause. G04/G05/G06 regression checks PASS; G07–G12 remain NOT_RUN. No human review of this patch has been asserted.
