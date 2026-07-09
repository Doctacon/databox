Status: done
Created: 2026-07-08
Updated: 2026-07-08
Parent: .10x/tickets/done/2026-07-08-build-birding-trip-copilot.md
Depends-On: .10x/tickets/2026-07-08-add-gbif-source-pipeline.md, .10x/tickets/2026-07-08-add-xeno-canto-source-pipeline.md, .10x/tickets/2026-07-08-add-open-meteo-trip-context-tool.md

# Model birding planner SQL interfaces

## Scope

Add SQLMesh models/views/tables that give the ADK planner and MotherDuck Dive stable SQL interfaces over birding evidence and persisted trip-plan artifacts.

In scope:

- Model planner-ready species/taxonomy lookup interfaces.
- Model recent/local observation interfaces using existing eBird/CDM data.
- Model GBIF-derived occurrence/taxonomy context after the GBIF raw schema exists.
- Model Xeno-canto-derived media/call metadata after the Xeno-canto raw schema exists.
- Define SQL interfaces for persisted trip plans, species recommendations, evidence items, Open-Meteo context, and tool traces.
- Add/adjust Soda contracts where needed for planner-facing modeled tables.
- Update docs/dictionary generation if new SQLMesh models are added.

Out of scope:

- dlt source implementation.
- Python ADK planner implementation.
- DeepEval implementation.
- Dive implementation.

## Acceptance criteria

- SQLMesh exposes stable planner-ready interfaces for observation, occurrence/taxonomy, media, persisted plans, recommendations, evidence, and tool traces.
- The models avoid inferring attributes/metrics beyond actual source schema columns and ratified trip-planning use cases.
- SQLMesh tests/contracts cover non-empty and core-key expectations where data exists.
- Native SQLMesh planning/tests pass for the affected project.
- `scripts/verify_dev.py` passes if affected by model changes.

## Evidence expectations

Record evidence with:

- SQLMesh commands run,
- model/table names created,
- sample query outputs or row counts,
- contract/test results,
- any source-schema limits affecting planner behavior.

## Progress and notes

- 2026-07-08: Ticket opened from parent Birding Trip Copilot plan.
- 2026-07-08: Added SQLMesh planner views for `birding_agent.species_lookup`, `birding_agent.recent_observation_evidence`, `birding_agent.gbif_occurrence_evidence`, and `birding_agent.xeno_canto_media_evidence`.
- 2026-07-08: Added physical persistence-table helper for `birding_agent.trip_plans`, `trip_plan_recommendations`, `trip_plan_evidence`, and `trip_plan_tool_traces`; aligned Open-Meteo evidence persistence with the widened evidence interface.
- 2026-07-08: Added Soda contracts and SQLMesh fixture tests for planner-facing models; updated Dagster analytics wiring and generated data dictionary pages.
- 2026-07-08: Validated with `sqlmesh test`, SQLMesh plan explanation, model renders, `dg check defs`, focused Open-Meteo pytest, ruff/format/mypy checks, and docs generation check. See `.10x/evidence/2026-07-08-birding-planner-sql-interfaces.md`.

## Blockers

None.
