Status: cancelled
Created: 2026-07-07
Updated: 2026-07-07
Parent: None
Depends-On: None

# Decommission legacy SQLMesh model layer before CDM workflow continuation

## Cancellation rationale

This ticket was opened from an incorrect premise: that the new CDM workflow implied replacing SQLMesh transformations with dlt hub transformations.

The user clarified that SQLMesh must remain the transformation layer. The CDM workflow remains useful as design/planning input, but implementation should generate CDM-aligned SQLMesh models, not dlt transformation scripts.

A replacement ticket tracks the corrected work: `.10x/tickets/done/2026-07-07-align-cdm-workflow-with-sqlmesh.md`.

## Historical observed surfaces

- SQLMesh models under `transforms/main/models/*/staging/`, `*/intermediate/`, `*/marts/`, and `analytics/fct_*.sql`.
- SQLMesh asset wiring in `packages/databox/databox/orchestration/domains/*.py` and `packages/databox/databox/orchestration/definitions.py`.
- Soda contracts for SQLMesh staging, source marts, and analytics marts under `soda/contracts/`.
- SQLMesh tests under `transforms/main/tests/test_models.yaml`.

## Explicit exclusions

- Do not remove SQLMesh as the transformation layer.
- Do not delete raw dlt source ingestion code.
- Do not delete `.schema/<cdm-name>/` annotation/ontology artifacts.

## References

- `.schema/environmental_observations/ontology.md`
- `.10x/skills/create-transformation/SKILL.md`
- `.10x/tickets/done/2026-07-07-align-cdm-workflow-with-sqlmesh.md`
