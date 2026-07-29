Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md
Depends-On: .10x/tickets/done/2026-07-12-investigate-analytics-asset-check-inventory.md

# Derive Soda checks from SQLMesh assets

## Scope

Replace the duplicate manual SQLMesh model-name lists in
`packages/databox/databox/orchestration/domains/analytics.py` with deterministic
composition from the existing `sqlmesh_project.specs` and modeled Soda contract
paths.

Create exactly one `soda_contract` check for every resolved SQLMesh model asset.
Fail definition-time validation when a resolved model lacks a matching contract
or when the contract dataset identity disagrees with the asset schema/model.

## Before and after semantics

Before:

- 18 SQLMesh model assets;
- 18 modeled Soda contracts;
- 14 resolved Soda checks;
- four missing checks documented in
  `.10x/research/2026-07-12-analytics-asset-check-inventory.md`.

After:

- the same 18 SQLMesh model assets;
- the same 18 contracts;
- exactly 18 resolved Soda checks, one per model;
- unchanged raw contracts, jobs, schedules, sensors, source assets, freshness,
  and SQLMesh model behavior.

## Acceptance criteria

- `_CDM_MODELS` and `_BIRDING_AGENT_MODELS` manual name lists are removed.
- `analytics.sqlmesh_asset_keys` derives deterministically from all 18
  `sqlmesh_project.specs` and retains the existing export contract.
- Every derived key has exactly one contract at
  `soda/contracts/<schema>/<model>.yaml` whose `dataset` is
  `databox/<schema>/<model>`.
- `analytics.asset_checks` contains exactly one `soda_contract` check per key.
- The four previously missing models now resolve checks.
- Missing, extra, duplicate, or identity-mismatched modeled contracts fail an
  executable parity test with useful diagnostics.
- The seven raw contracts remain outside modeled SQLMesh check composition.
- Resolved modeled asset keys stay 18/18; check coverage becomes 18/18; explicit
  jobs remain 14, schedules seven, sensors one.
- Dagster Definitions, focused parity tests, SQLMesh lint/tests, Soda contract
  structure, docs generation drift, Ruff, format, MyPy, diff, hashes, and empty
  staging checks pass.

## Explicit exclusions

- Executing Soda checks against the shared warehouse
- Changing contract contents, SQLMesh models, CDM, jobs, schedules, sensors,
  freshness, source behavior, or raw contract policy
- SQLMesh apply/plan, source refresh, provider calls, or warehouse mutation

## Evidence expectations

Record exact before/after asset/check inventories, parity failure cases,
unchanged orchestration inventories/hashes, commands/results, and runtime limits.

## Progress and notes

- 2026-07-12: Opened from proven 18-model/14-check drift. Missing checks are
  `birding_agent.arizona_species_catalog`,
  `environmental_observations.dim_bird_species_traits`,
  `environmental_observations.fact_bird_occurrence`, and
  `environmental_observations.fact_bird_sound_recording`.
- 2026-07-12: Removed both manual model lists. `sqlmesh_project.specs` now derives deterministic asset keys and one check per canonical identity-matched modeled contract; missing/extra/duplicate/mismatched/noncanonical contracts and invalid keys fail definition-time parity.
- 2026-07-12: Focused adversarial tests passed 10/10. Definitions resolve 18/18 modeled assets and 18/18 unique checks while jobs remain 14, schedules seven, and sensors one. SQLMesh lint/13 tests, 25-contract structure validation, docs/staging/platform-health drift, Ruff/format/MyPy, protected hashes, diff, and empty staging passed. Evidence: `.10x/evidence/2026-07-12-derived-soda-check-inventory.md`.
- 2026-07-12: Independent review `.10x/reviews/2026-07-12-derived-soda-check-inventory-review.md` passed every criterion. Retrospective: modeled checks must derive from SQLMesh specs plus contract identity, not a third manual inventory. Ticket closed.

## Blockers

None.

## References

- `.10x/research/2026-07-12-analytics-asset-check-inventory.md`
- `.10x/evidence/2026-07-12-analytics-asset-check-inventory.md`
- `docs/contracts.md`
- `packages/databox/databox/orchestration/_factories.py`
