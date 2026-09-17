# Stage-1 Seed-A Execution Failure

## Status

The exact approved Seed-A plan was invoked once and refused before the first successful resource creation. Its approval is consumed. The plan is now intentionally stale after the local fix and must never be retried.

## Attempted artifact

- Plan: `.recovery/iceberg/adcd0efc4e552f76/seed-a.plan.json`
- SHA-256: `87c9d768fe6d563aad03ef6d67dfa27ebf249d3cab59bc8ad669a0a91afeff9c`
- Result: generic safe refusal; no Recovery-A plan emitted

## Partial-state inspection

Bounded read-only inspection immediately after failure confirmed:

- zero generated Docker containers, running or stopped;
- no generated Docker network or PostgreSQL volume;
- zero S3 keys, object versions, or delete markers under the exact generated prefix;
- no Recovery-A manifest or damage marker;
- unchanged exact Seed-A file hash.

The recovery operator's exact credential, bucket-protection, and empty-prefix checks passed during a fake-stack replay that stopped at the mutation boundary. No canonical or unrelated resource was inspected by name or changed.

## Confirmed cause

`IsolatedStage1Stack._listed_names(...)` used Docker's `{{.Name}}` format field for every resource type. `docker container ls` exposes `{{.Names}}` instead, so the container-absence inventory failed before network creation.

A read-only differential probe reproduced the invalid-field error, proved `{{.Names}}` succeeds with the same daemon and filter, and confirmed the generated container remains absent. This ruled out the daemon, filter, runtime, AWS, settings, and plan bindings.

## Fix and validation

- Added a red-first regression test requiring `{{.Names}}` for containers and `{{.Name}}` for networks/volumes.
- Changed `_listed_names(...)` to select the resource-specific field.
- Regression test passed after the one-line fix.
- Original read-only Docker-inventory repro passed.
- 41 focused recovery-drill tests passed.
- 140 neighboring catalog/platform tests passed.
- Ruff, format, and diff checks passed.
- The old plan is rejected with `current runtime does not match the approved Seed-A plan`, proving its source/runtime binding cannot be reused after the fix.

## Next gate

A fresh explicit authorization is required to run mutation-free `prepare` again. A newly emitted plan then needs complete review and its own exact filename-and-SHA-256 approval before another Seed-A execution attempt.
