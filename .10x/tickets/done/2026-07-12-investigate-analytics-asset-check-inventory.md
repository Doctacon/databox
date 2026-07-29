Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md
Depends-On: .10x/tickets/done/2026-07-12-audit-warehouse-repository-simplicity.md

# Investigate analytics asset and check inventory

## Scope

Determine whether the manual SQLMesh/Soda model lists in
`packages/databox/databox/orchestration/domains/analytics.py` drift from current
SQLMesh models, CDM entities, Soda contracts, and resolved Dagster assets/checks.

This is a bounded correctness investigation. Do not repair inventory under this
ticket.

## Acceptance criteria

- Record exact declared SQLMesh models, CDM tables, Soda contracts, manual list
  entries, resolved Dagster asset keys, and resolved Soda check coverage.
- Classify every difference as intentional, stale documentation, missing check,
  missing asset, or non-governed model.
- Separate factual findings from any recommended derivation/codegen design.
- If repair is needed, open a focused implementation child with explicit
  before/after asset/check semantics and preservation checks.
- If no repair is needed, record an evidence-backed no-action rationale.
- Create a durable research/evidence record without mutating implementation.

## Explicit exclusions

- Adding/removing assets or checks
- SQLMesh apply, source refresh, or warehouse mutation
- Folding this correctness-sensitive behavior into generic cleanup

## Evidence expectations

Record commands, resolved inventories, discrepancies, runtime limits, and the
exact next owner or no-action conclusion.

## Progress and notes

- 2026-07-12: Opened because static audit found apparent inventory drift but did
  not load Dagster/SQLMesh or prove runtime impact.
- 2026-07-12: Metadata-only resolution proved 18 SQLMesh models/assets and 18 modeled contracts but only 14 Soda checks. The manual lists omit exactly `birding_agent.arizona_species_catalog`, `environmental_observations.dim_bird_species_traits`, `environmental_observations.fact_bird_occurrence`, and `environmental_observations.fact_bird_sound_recording`. No asset is missing; five non-CDM models and seven raw contracts are intentional. Research: `.10x/research/2026-07-12-analytics-asset-check-inventory.md`; evidence: `.10x/evidence/2026-07-12-analytics-asset-check-inventory.md`.
- 2026-07-12: Opened focused repair `.10x/tickets/done/2026-07-12-derive-soda-checks-from-sqlmesh-assets.md` with explicit 18-asset/14→18-check semantics and unchanged jobs/schedules/sensors/raw policy. Implementation was not changed under this investigation.
- 2026-07-12 retrospective: apparent duplicate authority was confirmed as correctness drift only after resolved metadata comparison; investigation remained separate from repair. Ticket closed with the repair as durable owner.

## Blockers

None.
