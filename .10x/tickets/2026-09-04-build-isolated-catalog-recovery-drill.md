Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md, .10x/tickets/done/2026-09-04-add-pgbackrest-catalog-protection.md

# Build isolated Polaris catalog recovery drill

## Scope

Add fail-closed automation that restores a selected pgBackRest backup/PITR target into a new isolated PostgreSQL volume, starts compatible Polaris recovery services without replacing restored realm state, validates the restored catalog conventionally and, when the primary warehouse remains readable, every canonical registered Iceberg table, and leaves production cutover manual.

Provide deterministic offline tests using temporary local fixtures/fakes. Do not download live backups, restore production objects, run providers, or mutate AWS in this ticket.

## Acceptance criteria

- Restore requires an explicit recovery target and a new empty destination; active catalog volumes and configured primary paths are rejected.
- Recovery runs with compatible pinned PostgreSQL, pgBackRest, and Polaris versions.
- Restored realm state is not silently bootstrapped or replaced.
- Writers remain disabled in the recovery environment.
- Validation derives expected registry-owned tables from the Databox source registry at the Git revision corresponding to the recovery point, enumerates restored catalog/namespace/table state through Polaris, and reports missing or unexpected state without a second hardcoded list.
- Missing metadata, manifests, data objects, permissions, status tables, or snapshot divergence fail visibly before cutover when the primary warehouse remains readable.
- Complete primary-warehouse loss is reported as requiring source rebuild and is not represented as object-level recovery or as satisfying the 60-minute catalog RTO.
- Documentation distinguishes catalog PITR, Iceberg snapshot rollback, source rebuild, and last-resort table re-registration.
- The drill records start/end timestamps and computes achieved RPO/RTO but does not report objectives as proven in offline tests.
- Adversarial tests cover non-empty target, active-volume alias, malformed timestamp, absent backup/WAL, registry/restored-state mismatch, missing object, failed table scan, accidental bootstrap, and secret redaction.
- Focused tests, Compose rendering, Ruff, format, MyPy, secret scan, and diff checks pass without live external mutation.

## Explicit exclusions

- Live restore, timed guarantee, AWS apply, or production cutover.
- Iceberg object restoration, recovery buckets, replication, or scheduled warehouse copies.
- Iceberg snapshot expiration, orphan deletion, or compaction.
- Changing source/model semantics.

## References

- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md`
- `.10x/tickets/done/2026-09-04-add-pgbackrest-catalog-protection.md`

## Evidence expectations

Record adversarial restore-safety cases, registry-derived restored-table validation cases, elapsed-time calculation, changed files, exact commands/results, and no-live-AWS/no-production-restore limits.

## Progress and notes

- 2026-09-04: Opened from the ratified disaster-recovery architecture.
- 2026-09-04: Timeboxed implementation added a preparation-only recovery helper that requires a zoned timestamp, rejects the active and non-empty destinations, creates only an empty isolated target, keeps writers disabled/bootstrap forbidden, and computes RPO/RTO without claiming proof. Focused adversarial tests and runbook distinctions were added. The ticket remains open because actual pgBackRest restore composition, conventional registry-derived catalog/table validation, and full failure-path tests are not yet implemented; no live restore ran.

## Blockers

Depends on catalog-only infrastructure simplification, then actual restore composition and catalog/table validation.
