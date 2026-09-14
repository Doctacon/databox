Status: blocked
Created: 2026-09-10
Updated: 2026-09-10
Parent: .10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md
Depends-On: .10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md

# Build controlled Iceberg object-version restoration

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `1ff6924d83c2824c5b2a4f79b7df3446cbfd88f9b07ccd4764378e14162cda32`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/tickets/2026-09-10-build-iceberg-object-version-restore.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Scope and execution state

Own the unfinished contract for a bounded operator workflow that restores selected retained S3 versions into a usable Iceberg table, then implement only after its governing specification is ratified. This is a blocked shaping ticket, not an executable instruction to choose recovery semantics.

## References

- `.10x/specs/iceberg-object-version-restore.md` — draft; all candidate choices remain unratified.
- `.10x/specs/iceberg-warehouse-version-retention.md`
- `.10x/specs/iceberg-writer-version-delete-denial.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`
- `scripts/platform/catalog_recovery.py`, `scripts/platform/catalog_recovery_validate.py`, `packages/databox/databox/destinations/iceberg.py` — reuse candidates, not authority for a new S3-write path.

## Contract required before executable acceptance criteria

The draft spec must settle recovery selection (keys/versions versus table snapshot/catalog target), destination (original keys versus isolated prefix with valid rewritten paths), existing/live version conflict behavior, catalog registration/pointer handling, operator identity/permissions, concurrency and writer fencing, preview/apply confirmation, bounded failure/retry/resume behavior, artifacts/cleanup, and operational owner. Exact success/error and idempotency scenarios must then be approved and mapped to tests.

Recommendations live only in the draft spec. Do not infer “latest good” from filenames, assume that copying metadata rewrites Iceberg paths, add an administrator role, or equate a routine writer's ordinary DeleteObject permission with authority to remove delete-marker versions.

## Exclusions and write boundary

Until unblocked: record-only shaping and source inspection; no implementation file, test, CLI, fixture, generated plan, credential grant, or cloud operation. Later implementation still excludes actual primary-data restoration, production cutover, table rollback, policy expansion, source refresh, and automatic cleanup unless separately ratified.

## Evidence expectations

Before release, link the activated focused spec and exact user decisions. After separately authorized implementation, record focused synthetic tests for the ratified selection/conflict/failure behavior, regression evidence preserving catalog recovery and secret boundaries, changed files, independent review, and live-proof limits. Split distinct outcomes if the agreed design requires more than this bounded workflow.

## Progress and notes

- 2026-09-10: Created because the user requested tickets for the protection/recovery work. Versioning/retention and version-delete denial are confirmed; a category-level request for a recovery command does not settle write semantics or permissions.

## Blockers

Inspection dependency; every unresolved draft contract item above; active specification and concrete acceptance criteria; and subsequent implementation authorization. No restoration algorithm or credential policy is approved by this ticket.
