Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md
Depends-On: .10x/tickets/done/2026-07-12-consolidate-canonical-dlt-source-registry.md

# Reconcile canonical raw-table inventory

## Scope

Repair the source-observed mismatch between canonical registry `raw_tables` and active dlt resources, limited to:

- eBird `taxonomy` and `region_stats`;
- NOAA `datasets`;
- generated `analytics.platform_health` SQL required by the registry change;
- refresh inspection, codegen, and focused tests/evidence required for coherence.

## Acceptance criteria

- Registry inventory includes every current eBird and NOAA dlt resource without changing provider queries or write behavior.
- Generated platform-health SQL matches the canonical registry.
- Refresh inspection expects the added existing raw tables and preserves all other behavior.
- Focused registry, codegen, and refresh inspection tests pass.
- No provider request, refresh, SQLMesh apply, or warehouse mutation occurs.

## Explicit exclusions

- New sources/tables beyond the three named source-observed omissions
- Source semantics, schedules, SQLMesh models other than required generated platform health, or runtime data mutation

## Evidence expectations

Record before/after inventory, generated diff, focused commands/results, and no-runtime-write limits.

## Progress and notes

- 2026-07-12: Opened when canonical-registry implementation confirmed the active source functions expose three tables omitted from current registry inventory. The parent directed preservation of existing behavior in the consolidation ticket and a bounded dependent repair.
- 2026-07-12: Added exactly eBird `taxonomy`/`region_stats` and NOAA `datasets` to the canonical registry; no other source inventory changed.
- 2026-07-12: Regenerated only `analytics.platform_health` from the registry and added exact inventory plus temporary-DuckDB refresh-inspection coverage.
- 2026-07-12: Focused validation passed: 35 tests, codegen drift check, Ruff, formatting, MyPy, diff check, and empty staging. Evidence: `.10x/evidence/2026-07-14-canonical-raw-table-inventory-reconciliation.md`.
- 2026-07-12: Parent reproduced 35 focused passing tests plus codegen, static, diff, and staging checks. Fresh review passed: `.10x/reviews/2026-07-14-canonical-raw-table-inventory-reconciliation-review.md`.
- 2026-07-12: Retrospective complete. The discovery is fully absorbed into the canonical registry/spec graph; no repeatable new procedure or additional unfinished work remains, so no separate knowledge, skill, or follow-up record is required.

## Blockers

None. The canonical registry consolidation dependency is done.

## References

- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md`
