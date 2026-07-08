Status: done
Created: 2026-07-07
Updated: 2026-07-07
Parent: None
Depends-On: None

# Align CDM workflow with SQLMesh as transformation layer

## Scope

Keep the annotate-sources → create-ontology → generate-cdm design workflow, implement the approved environmental observations CDM as SQLMesh models, validate those models, then retire superseded source-specific SQLMesh staging/intermediate/mart models after validation.

## Context

The user clarified that SQLMesh must remain the transformation layer. dlt remains ingestion. CDM artifacts are design contracts that should guide SQLMesh model generation and cleanup of older ad hoc models.

## Acceptance criteria

- `.10x/skills/create-transformation/SKILL.md` instructs agents to write SQLMesh models under `transforms/main/models/<cdm-name>/`, not dlt transformation scripts.
- The old dlt-hub transformation premise is removed from project-level Pi skill exposure.
- `.schema/environmental_observations/CDM.dbml` exists and expresses the trusted Kimball CDM contract.
- CDM-aligned SQLMesh models exist under `transforms/main/models/environmental_observations/`.
- CDM models validate before any legacy SQLMesh model is retired.
- Superseded legacy SQLMesh staging/intermediate/source mart and legacy analytics fact models are removed only after CDM validation.
- Dagster wiring, Soda contracts, SQLMesh tests, and docs no longer point at removed legacy models.
- Operational `analytics.platform_health` is retained unless explicitly superseded.

## Progress and notes

- 2026-07-07: Rewrote `.10x/skills/create-transformation/SKILL.md` to make SQLMesh the transformation target and dlt ingestion-only.
- 2026-07-07: Cancelled `.10x/tickets/cancelled/2026-07-07-decommission-legacy-sqlmesh-model-layer.md`, which was based on the incorrect premise that SQLMesh should be removed as a transform layer.
- 2026-07-07: User explicitly approved continuing with trusted CDM generation, SQLMesh implementation, validation, and retirement of superseded ad hoc SQLMesh models.
- 2026-07-07: Generated `.schema/environmental_observations/CDM.dbml`.
- 2026-07-07: Added 9 CDM SQLMesh models under `transforms/main/models/environmental_observations/` and CDM Soda contracts under `soda/contracts/environmental_observations/`.
- 2026-07-07: Validated CDM models in SQLMesh dev before deleting legacy models.
- 2026-07-07: Removed superseded legacy source-specific SQLMesh staging/intermediate/mart models and legacy analytics fact models. Retained `analytics.platform_health`.
- 2026-07-07: Updated Dagster wiring so source domains own ingestion and analytics wiring owns CDM/operational SQLMesh assets.
- 2026-07-07: Updated metrics, docs, source-layout/new-source scaffolding, and tests to reference the CDM model layer.
- 2026-07-07: `task ci`, `task full-refresh`, `dg check defs`, `sqlmesh test`, and `scripts/verify_dev.py` passed. See `.10x/evidence/2026-07-07-cdm-sqlmesh-migration.md`.
- 2026-07-07: Review passed. See `.10x/reviews/2026-07-07-cdm-sqlmesh-migration-review.md`.

## Blockers

None.

## Explicit exclusions

- Do not replace SQLMesh with dlt hub transformations.
- Do not delete existing SQLMesh models until CDM-aligned SQLMesh models exist and validate.
- Do not change dlt ingestion architecture.

## References

- `.10x/skills/create-transformation/SKILL.md`
- `.10x/skills/generate-cdm/SKILL.md`
- `.schema/environmental_observations/ontology.md`
- `docs/adr/0002-sqlmesh-over-dbt.md`
- `docs/adr/0003-single-sqlmesh-project.md`
- `docs/adr/0005-dagster-as-sole-orchestrator.md`
