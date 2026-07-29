Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md
Depends-On: .10x/tickets/done/2026-07-12-audit-warehouse-repository-simplicity.md

# Simplify public warehouse onboarding

## Scope

Create one coherent data-engineer path across the public repository surface
without changing command or operational semantics.

- distinguish offline evaluation from optional credentialed ingestion in the
  README and avoid duplicate `.env` creation;
- make `docs/index.md` the warehouse start page and remove stale README/
  orchestration descriptions;
- move Rufous-only command and runbook sections into a dedicated Rufous
  operations page, leaving concise links at their former warehouse locations;
- group MkDocs navigation into Start, Warehouse, Extend, Operate, Rufous, and
  Architecture while preserving existing URLs where possible.

## Acceptance criteria

- A data engineer can find purpose, offline evaluation, live build, inspection,
  and extension paths from README/docs home.
- README commands agree exactly with Taskfile behavior.
- Warehouse commands/runbook are not interrupted by long Rufous procedures.
- All moved Rufous operational content remains present and discoverable.
- Existing page URLs remain or have an explicit redirect/link rationale.
- Local links, strict MkDocs, docs drift checks, and any docs-sensitive tests pass.

## Explicit exclusions

- Changing Task commands, warehouse behavior, or Rufous operations
- Rewriting architecture semantics
- Merging `docs/new-source.md` with `docs/source-layout.md`
- Editing generated dictionary pages by hand

## Evidence expectations

Record before/after navigation, exact moved sections, command parity, link/build
results, and preserved Rufous content.

## Progress and notes

- 2026-07-12: Opened from the public-path finding in the warehouse simplicity
  audit. The root README remains details-on-demand and warehouse-first.
- 2026-07-12: First implementation simplified onboarding and moved Rufous operations; 20 docs-sensitive tests and strict docs checks passed. Independent review found three missing legacy `docs/index.md` fragment anchors (`whats-here`, `architecture-decisions`, `regenerate`). Repair remains active.
- 2026-07-12: Corrected README quickstart parity: `task install` owns conditional `.env` creation, `task ci` is the offline evaluation path, and credentialed `task full-refresh`/Dagster inspection are explicitly optional. Both warehouse-first Mermaid diagrams and the modeling-skill chain remain unchanged.
- 2026-07-12: Rebuilt `docs/index.md` as the data-engineer start page; moved the exact Rufous command and trip-calendar runbook bodies to new stable `docs/rufous-operations.md`; left concise links plus compatibility anchors at all former deep-link locations.
- 2026-07-12: Grouped MkDocs navigation into Start, Warehouse, Extend, Operate, Rufous, and Architecture without removing existing pages/URLs. Updated the Rufous public-doc contract test to inspect the new owner page.
- 2026-07-12: Exact preservation checks confirmed 215 moved command lines and 28 moved trip-calendar lines; local links, four compatibility anchors, README/Task parity, two Mermaid diagrams, 20 generated docs, strict MkDocs, 20 docs-sensitive tests, Ruff, format, diff, and empty staging passed. Evidence: `.10x/evidence/2026-07-12-public-warehouse-onboarding-simplification.md`.
- 2026-07-12: Independent review found three missing former docs-home fragments: `whats-here`, `architecture-decisions`, and `regenerate`. Added unobtrusive compatibility anchors to the new start page plus `tests/test_docs_navigation.py` regression coverage; no command or content semantics changed.
- 2026-07-12: Post-repair validation passed 21 docs-sensitive tests, 28-page local-link scan, all seven compatibility anchors including rendered HTML, 20-file docs drift, strict MkDocs, Ruff, format, diff, and empty staging. Evidence updated at `.10x/evidence/2026-07-12-public-warehouse-onboarding-simplification.md`.
- 2026-07-12: Independent final review `.10x/reviews/2026-07-12-public-warehouse-onboarding-review.md` passed every criterion. Retrospective: public restructuring must preserve fragment compatibility as well as page URLs; regression coverage now owns those anchors. Ticket closed.

## Blockers

None.
