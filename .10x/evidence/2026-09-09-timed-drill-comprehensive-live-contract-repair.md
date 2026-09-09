Status: recorded
Created: 2026-09-09
Updated: 2026-09-09

# Timed drill comprehensive live-contract repair

## Trigger

Three operator attempts exposed mock/live drift: incorrect active-port expectations, root pgBackRest invocation, and asynchronous archival inheriting the active container's expired startup token. The third attempt committed marker `databox_recovery_drill_y0puu4ucgfgbx81p` but failed before restore; no recovery volume, network, or container was created.

A subsequent three-lane end-to-end audit stopped the retry cycle and reviewed every concrete command, failure boundary, metric, and runtime assumption together.

## Repairs

- pgBackRest PITR target rendering preserves six fractional-second digits in UTC.
- Explicit marker and cleanup WAL pushes are synchronous and run as `postgres` with the fresh session.
- Recovery PostgreSQL receives no backup credentials and runs with archival disabled.
- Recovery Polaris container configuration is secret-free. Polaris runs through a detached exec child environment and is always stopped after validation or failure; the stopped container remains preserved.
- Marker reconciliation is idempotent: exact absence continues to synchronous WAL proof; a present relation must be exactly one ordinary `public` table owned by `polaris` before DROP.
- Cleanup marker drop, WAL archival, and Polaris quiescence are tracked separately with bounded redacted diagnostics and preserved primary failure context.
- RTO begins before CLI authentication. Results retain metrics and exit nonzero when RPO exceeds 300 seconds or RTO exceeds 3,600 seconds.
- MFA-issued credentials require at least 15 minutes remaining before mutation. This protects against near-expiry cached sessions but does not guarantee the 60-minute objective.
- Docker absence accepts only a not-found response; daemon, permission, and ambiguous failures stop before mutation.
- Catalog success is registry-derived: expected count must be positive, validated must equal expected, and failed must be zero; the current registry still yields 25.
- `drill --reconcile-marker ...` combines known-marker reconciliation and the new drill behind one TTY authentication.

## Disposable and read-only runtime proof

Without AWS access, secrets, network access, or active mounts, disposable pinned-image probes proved:

- pgBackRest 2.59.1 exposes `archive-async` and accepts `--no-archive-async help archive-push`;
- the pinned PostgreSQL image resolves `postgres` to UID 999;
- the Polaris 1.7.0 image contains executable `/opt/jboss/container/java/run/run-java.sh`, `/bin/sh`, and `/usr/bin/sleep`.

A read-only active `SELECT clock_timestamp()` through `psql -qAtX` produced exactly one timestamp row. Docker inspection reconfirmed both active services running/healthy, PostgreSQL unexposed, Polaris bound only to loopback 8181/8182, and both attached only to `databox-iceberg_default`.

Focused validation passed 112 recovery/validator tests without coverage, Ruff check/format, MyPy, the 927-file secret scan, Task dry-run, and `git diff --check`.

## Safety boundary

No AWS call, active SQL mutation, marker cleanup, restore, or drill was executed during this repair. Disposable probe containers used `--rm --network none` with no mounts or credentials. No credential file, new script, profile mount, cutover, or recovery-resource deletion was added.
