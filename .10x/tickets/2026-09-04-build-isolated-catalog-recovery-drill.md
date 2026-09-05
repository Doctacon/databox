Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-declare-aws-recovery-infrastructure.md, .10x/tickets/2026-09-04-add-pgbackrest-catalog-protection.md

# Build isolated Polaris catalog recovery drill

## Scope

Add fail-closed automation that restores a selected pgBackRest backup/PITR target into a new isolated PostgreSQL volume, starts compatible Polaris recovery services without replacing restored realm state, validates the catalog inventory and every canonical registered Iceberg table, supports bounded selected-object recovery guidance, and leaves production cutover manual.

Provide deterministic offline tests using temporary local fixtures/fakes. Do not download live backups, restore production objects, run providers, or mutate AWS in this ticket.

## Acceptance criteria

- Restore requires an explicit recovery target and a new empty destination; active catalog volumes and configured primary paths are rejected.
- Recovery runs with compatible pinned PostgreSQL, pgBackRest, and Polaris versions.
- Restored realm state is not silently bootstrapped or replaced.
- Writers remain disabled in the recovery environment.
- Validation compares catalog/schema/namespace/table inventory and verifies each registry-owned table pointer through the canonical registry/Polaris interface without a second hardcoded source list.
- Missing metadata, manifests, data objects, permissions, status tables, or snapshot divergence fail visibly before cutover.
- Object recovery is bounded to explicit keys/versions or a reviewed table scope and never deletes from the recovery bucket.
- Documentation distinguishes PITR, Iceberg snapshot rollback, missing-object restoration, and last-resort table re-registration.
- The drill records start/end timestamps and computes achieved RPO/RTO but does not report objectives as proven in offline tests.
- Adversarial tests cover non-empty target, active-volume alias, malformed timestamp, absent backup/WAL, inventory mismatch, missing object, failed table scan, accidental bootstrap, and secret redaction.
- Focused tests, Compose rendering, Ruff, format, MyPy, secret scan, and diff checks pass without live external mutation.

## Explicit exclusions

- Live restore, timed guarantee, AWS apply, or production cutover.
- Broad automatic object restoration.
- Iceberg snapshot expiration, orphan deletion, or compaction.
- Changing source/model semantics.

## References

- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/specs/iceberg-object-recovery.md`
- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/tickets/2026-09-04-declare-aws-recovery-infrastructure.md`
- `.10x/tickets/2026-09-04-add-pgbackrest-catalog-protection.md`

## Evidence expectations

Record adversarial restore-safety cases, inventory/table validation cases, elapsed-time calculation, changed files, exact commands/results, and no-live-AWS/no-production-restore limits.

## Progress and notes

- 2026-09-04: Opened from the ratified disaster-recovery architecture.
- 2026-09-04: Timeboxed implementation added a preparation-only recovery helper that requires a zoned timestamp, rejects the active and non-empty destinations, creates only an empty isolated target, keeps writers disabled/bootstrap forbidden, and computes RPO/RTO without claiming proof. Focused adversarial tests and runbook distinctions were added. The ticket remains open because actual pgBackRest restore composition, canonical catalog/table inventory validation, bounded object-version restoration, and full failure-path tests are not yet implemented; no live restore ran.

## Blockers

Depends on completion of the remaining pgBackRest ticket work, then actual restore composition, catalog/table validation, and bounded object recovery.
