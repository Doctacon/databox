Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md
Depends-On: None

# Audit warehouse repository simplicity

## Scope

Perform a read-only audit of the public repository surface and warehouse core
for a data-engineer audience. Identify proven duplication, dead paths,
contradictory ownership, misleading naming, and avoidable navigation cost.

Inspect README/docs, Taskfile and scripts, root layout, Python package exports
and imports, dlt source boundaries, orchestration/config/quality packages,
SQLMesh/Soda/schema artifacts, and generated-versus-authored documentation.
Treat Rufous internals only as a consumer boundary, not a refactoring target.

## Acceptance criteria

- Map the shortest newcomer path from clone to understanding/running/extending
  the warehouse.
- Identify each candidate cleanup with exact paths and reference/import evidence.
- Classify candidates as delete, consolidate, rename/move, clarify, or keep.
- Reject speculative cleanup and explain why large or apparently legacy surfaces
  remain required when evidence shows active compatibility behavior.
- Separate independent implementation slices and dependencies.
- Define behavior-preservation checks for each recommended slice.
- Create `.10x/research/2026-07-12-warehouse-repository-simplicity-audit.md`.
- Do not edit implementation, docs, configuration, generated artifacts, or tests.

## Explicit exclusions

- Running tests/builds/generators or commands that mutate project state
- Implementing cleanup
- Rufous internal decomposition
- Provider, SQLMesh, or warehouse runtime operations

## Evidence expectations

Record inspected paths, import/reference searches, authoritative owners,
non-authoritative duplicates, rejected candidates, limits, and recommended
child-ticket boundaries.

## Progress and notes

- 2026-07-12: Opened from the ratified warehouse-first cleanup policy. No
  implementation is authorized until this audit produces bounded slices.
- 2026-07-12: Completed the read-only audit at `.10x/research/2026-07-12-warehouse-repository-simplicity-audit.md`. Recommended independent slices: runtime-repository hygiene, public warehouse onboarding, package dependency direction, obsolete smoke-runner deletion, and a separately gated analytics asset/check inventory reconciliation. No implementation/docs/config/tests were edited and no test/build/runtime command was run.
- 2026-07-12: Parent opened bounded implementation/investigation children and a final verification gate from the audit findings. Retrospective learning is captured in `.10x/knowledge/warehouse-first-cleanup.md`; no additional skill is warranted. Audit closed.

## Blockers

None.

## References

- `.10x/knowledge/warehouse-first-cleanup.md`
- `.10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md`
