Status: blocked
Created: 2026-09-10
Updated: 2026-09-10
Parent: .10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md
Depends-On: .10x/tickets/2026-09-10-apply-iceberg-warehouse-version-protection.md, .10x/tickets/2026-09-10-build-iceberg-object-version-restore.md

# Prove recovery with a disposable Iceberg table

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `f8e71ec2fbdb7ae23bcc7f6e1f1faa40196bcea1274d862cf43b5aaeb19dbc04`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/tickets/2026-09-10-prove-iceberg-object-version-recovery.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Scope and execution state

Own a future isolated, synthetic-data proof of the configured version history and selected table-restoration workflow. No authoritative table/object may be damaged to test recovery. This is blocked until the restore contract and an exact live drill plan are approved; the scenarios below describe required proof areas, not permission to invent fixtures or run deletes.

## References

- `.10x/specs/iceberg-object-version-restore.md` — draft; must be ratified before test/live use.
- `.10x/specs/iceberg-warehouse-version-retention.md`
- `.10x/specs/iceberg-writer-version-delete-denial.md`
- `.10x/specs/polaris-catalog-continuity.md` — preserve isolated catalog/no-cutover boundaries.
- The deployment/tooling dependencies and their evidence/reviews, when available.

## Proof areas to concretize before execution

- A new, verified run-owned disposable catalog/table/prefix and deterministic synthetic rows, with no references into authoritative table locations.
- Exact permitted overwrite and ordinary-delete operations create recoverable prior versions/delete markers. Every intended mutation is listed before authorization.
- An exact disposable version-specific delete by the routine writer is denied for the expected policy reason, not merely because credentials/network/another permission failed. The run must be safe even if this negative test unexpectedly succeeds.
- The selected recovery method restores a coherent table snapshot: catalog/metadata agreement and readable required manifests, data/delete files, with exact expected synthetic query results. One successfully copied object is insufficient.
- Current-data non-expiration and 30-day configuration are verified without shortening retention or pretending a short drill observed 30 days of lifecycle processing.
- No primary data, active services, unrelated AWS settings, or previous recovery artifacts change. No cutover occurs. Timing is reported without inventing a warehouse RTO.
- Run-owned artifacts and cleanup authority are explicit for success and failure; do not silently make automatic cleanup part of this ticket or leave final-answer-only follow-up work.

These proof areas must become exact acceptance scenarios through the activated restore spec and approved run plan before the ticket is executable.

## Evidence expectations

Sanitized plan/approval, verified identities and run ownership, exact mutated disposable keys/version IDs, expected and observed denial, snapshot/object/query results, pre/post primary-state checks, elapsed time, failure/cleanup state, independent review, and honest limits. Preserve only synthetic data and bounded secret-free diagnostics. Configuration and a synthetic table drill do not prove regional/account/bucket-loss recovery or universal 30-day catalog-to-warehouse PITR.

## Explicit exclusions

Authoritative warehouse deletion/overwrite, version purging, changing actual retention for faster testing, full source refresh, automatic cutover, new credentials/permissions, active-stack restarts, and deletion of preserved catalog-recovery resources.

## Progress and notes

- 2026-09-10: Created as the separately authorized proof stage; no fixtures, tests, cloud resources, or writes were created.

## Blockers

Deployment and tooling dependencies; active restore specification; exact synthetic fixtures, catalog/prefix ownership, operator authority, mutations, assertions, concurrency/propagation handling and artifact lifecycle; then independent plan review and explicit live-drill approval. This ticket is not executable.
