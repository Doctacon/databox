Status: recorded
Created: 2026-09-08
Updated: 2026-09-08
Target: 2b96db6
Verdict: concerns

# Isolated restore runner safety review

## Finding

**P1 — target-volume creation has a check/create race.** `scripts/platform/catalog_recovery.py` checks absence with `docker volume ls`, then uses idempotent `docker volume create` before mounting and modifying the target. A volume created by another process between those operations would be accepted and modified. Existing tests model only an always-absent target.

The runner must create the volume with a per-execution unguessable ownership label, inspect and require that exact label before either container mount, and refuse without `docker run` when ownership cannot be proven. It must not delete an unowned volume.

## Verdict

Concerns. No live restore may be authorized until this finding is repaired and independently re-reviewed.

## Residual risk

No live restore has run. Other reviewed safety properties passed: prepare-only is nonmutating apart from listing volumes; secret values do not enter arguments; and generated commands contain no active socket/port, archive push, bootstrap, delta, deletion, PostgreSQL startup, cleanup, or cutover.
