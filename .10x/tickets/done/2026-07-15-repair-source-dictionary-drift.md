Status: done
Created: 2026-07-15
Updated: 2026-07-15
Parent: .10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md
Depends-On: .10x/tickets/done/2026-07-12-reconcile-canonical-raw-table-inventory.md

# Repair generated source dictionary drift

## Scope

Repair the exact aggregate-verification blocker recorded in `.10x/evidence/2026-07-15-unified-source-contract-aggregate-verification.md`:

- regenerate `docs/dictionary/analytics/platform_health.md` from the current SQLMesh/source registry state;
- include exactly the newly modeled external dependencies `raw_ebird.region_stats`, `raw_ebird.taxonomy`, and `raw_noaa.datasets`;
- run generated-doc drift and strict documentation validation;
- record bounded evidence.

## Acceptance criteria

- `scripts/generate_docs.py --check` passes.
- The platform-health dictionary lists the three named existing dependencies and no unrelated hand-authored change.
- `mkdocs build --strict`, relevant docs tests/checks, and `git diff --check` pass.
- No provider request, source refresh, SQLMesh apply, warehouse connection/write, model call, or product/runtime action occurs.

## Evidence expectations

Record the pre-repair drift, exact generated diff, commands/results, and no-runtime-side-effect limits.

## Explicit exclusions

- Any other documentation rewrite or model/source behavior change
- Full refresh, SQLMesh plan/apply, provider calls, or warehouse mutation
- Repair of unrelated warnings or generated files

## Progress and notes

- 2026-07-15: Opened from the failed required docs-drift gate in aggregate verification. The exact generated diff is three dependency bullets in one dictionary page.
- 2026-07-15: Ran the repository generator. Only `docs/dictionary/analytics/platform_health.md` changed, adding exactly `raw_ebird.region_stats`, `raw_ebird.taxonomy`, and `raw_noaa.datasets`.
- 2026-07-15: Generated-doc drift, strict MkDocs build, generator Ruff/format, exact dependency/changed-file assertions, diff check, and empty staging passed. Evidence: `.10x/evidence/2026-07-15-source-dictionary-drift-repair.md`.
- 2026-07-15: Parent reproduced the exact three-line generated diff, docs drift check, strict build, diff check, and empty staging. Review passed: `.10x/reviews/2026-07-15-source-dictionary-drift-repair-review.md`.
- 2026-07-15: Retrospective complete. This was a deterministic generated-doc synchronization with no new reusable procedure or unfinished work; existing generator/check commands are sufficient.

## Blockers

None.

## References

- `.10x/evidence/2026-07-15-unified-source-contract-aggregate-verification.md`
- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/tickets/done/2026-07-12-verify-unified-source-contract-and-ci.md`
