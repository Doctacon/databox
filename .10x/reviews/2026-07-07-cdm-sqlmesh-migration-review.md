Status: recorded
Created: 2026-07-07
Updated: 2026-07-07
Target: .10x/tickets/done/2026-07-07-align-cdm-workflow-with-sqlmesh.md
Verdict: pass

# Review: CDM SQLMesh migration

## Target

Working-tree changes for `.10x/tickets/done/2026-07-07-align-cdm-workflow-with-sqlmesh.md`.

## Findings

### Pass: SQLMesh remains the transformation layer

The new model layer is under `transforms/main/models/environmental_observations/`, and dlt source domains retain ingestion-only responsibility.

### Pass: legacy model layer retired

Legacy source-specific SQLMesh model files and model-specific Soda contracts were removed. A stale-reference scan for exact retired names returned no matches after updating tests/docs.

### Pass: Dagster definitions and SQLMesh tests validate

- `dg check defs --use-active-venv` loaded definitions successfully.
- `sqlmesh test` ran 2 tests successfully.
- `task ci` passed with 119 pytest tests.

### Minor: CDM SQLMesh unit-test coverage is intentionally thin

There are 2 SQLMesh unit tests for 9 CDM models. This is acceptable for the migration because destination-native checks and Soda contracts cover row/key/FK integrity, but future semantic changes should add targeted SQLMesh tests.

### Resolved: reviewer-reported idempotency failure not reproduced

A read-only reviewer reported a one-off failure in `packages/databox-sources/tests/ebird/test_idempotency.py`. The exact targeted test was rerun and passed, and the full `task ci` suite also passed.

### Resolved: stale OpenLineage mock asset key

The reviewer found a stale mocked `sqlmesh/ebird/stg_ebird_observations` asset key in `tests/test_openlineage_sensor.py`. It was updated to `sqlmesh/environmental_observations/fact_bird_observation`; the targeted test and full CI passed.

## Verdict

Pass. Residual risk is limited to future semantic expansion of the CDM model layer; current structural/key/FK checks, Soda contracts, SQLMesh tests, Dagster definition load, and full refresh evidence support completion.
