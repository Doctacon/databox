Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md
Depends-On: .10x/tickets/done/2026-07-12-audit-warehouse-repository-simplicity.md

# Break source package dependency cycle

## Scope

Remove the unsupported `databox-sources` → `databox` runtime dependency while
preserving the supported one-way boundary: `databox` composes independently
importable source definitions from `databox-sources`.

Update only package metadata/lockfile and stale package descriptions required by
that boundary.

## Acceptance criteria

- `packages/databox-sources` no longer declares a runtime dependency on `databox`.
- `packages/databox` continues to depend on `databox-sources`.
- Runtime code under `databox_sources/**` contains no `databox` import.
- Source definitions import without the orchestration package being required.
- Lockfile/workspace metadata is coherent.
- Source profile tests, canonical builder tests, Dagster definitions, package
  imports, static checks, and full relevant tests pass.
- The `databox` package description names current quality/codegen behavior rather
  than the deleted generic quality engine.

## Explicit exclusions

- Merging the two packages
- Moving source tests or changing source/provider behavior
- Changing public Python APIs beyond dependency metadata

## Evidence expectations

Record dependency graph before/after, import scan, lockfile delta, isolated
source import proof, definitions load, and test/static results.

## Progress and notes

- 2026-07-12: Opened from the high-confidence metadata-cycle finding in the
  warehouse simplicity audit.
- 2026-07-12: Removed only the unsupported `databox-sources` → `databox` runtime metadata edge and unused workspace-source entry; preserved `databox` → `databox-sources`; corrected the stale databox package description.
- 2026-07-12: Regenerated `uv.lock` offline. The reverse edge was removed and stale workspace lock versions were synchronized from 0.5.0 to existing 0.6.0 package metadata.
- 2026-07-12: Runtime import scan found zero `databox` imports; an explicit import blocker still allowed 17 imports: the `databox_sources` package root plus all 16 discovered submodules. Complete source profiles passed 60 tests/seven snapshots offline, builder/registry passed 30 tests, Definitions loaded, workspace imports/Ruff/format/MyPy/lock/diff/staging passed, and the shared warehouse hash stayed byte-identical. Evidence: `.10x/evidence/2026-07-12-source-package-dependency-direction.md`.
- 2026-07-12: Independent review passed every criterion and corrected only the import-count wording. Retrospective: package metadata must follow runtime import direction; workspace test coupling is not a runtime dependency. Ticket closed.

## Blockers

None.
