Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-derive-soda-checks-from-sqlmesh-assets.md, .10x/research/2026-07-12-analytics-asset-check-inventory.md

# Derived Soda check inventory

## What was observed

The implementation removes `_CDM_MODELS` and `_BIRDING_AGENT_MODELS` from
`analytics.py`. The 18 `sqlmesh_project.specs` are now the modeled-asset
authority. Definition-time parity pairs each deterministic asset key with exactly
one canonical `soda/contracts/<schema>/<model>.yaml` file whose dataset is
`databox/<schema>/<model>`.

Before/after resolved metadata:

- SQLMesh models/assets: 18 → 18;
- modeled Soda contracts: 18 → 18;
- `soda_contract` checks: 14 → 18;
- explicit jobs: 14 → 14;
- schedules: 7 → 7;
- sensors: 1 → 1.

The four newly covered checks are
`birding_agent.arizona_species_catalog`,
`environmental_observations.dim_bird_species_traits`,
`environmental_observations.fact_bird_occurrence`, and
`environmental_observations.fact_bird_sound_recording`.

Seven `raw_*` Soda contracts remain outside modeled check composition.

## Fail-closed behavior

Focused tests prove deterministic ordering and reject:

- missing modeled contracts;
- extra modeled contracts;
- duplicate modeled dataset identities;
- mismatched dataset identities;
- noncanonical `.yml` or nested modeled contract paths;
- duplicate or malformed SQLMesh asset keys.

Raw contract paths are explicitly ignored by modeled parity.

## Procedure and results

- `.venv/bin/pytest --no-cov -q tests/test_analytics_contract_inventory.py` — **10 passed**.
- `.venv/bin/dg check defs --use-active-venv` — all Definitions loaded.
- Resolved inventory assertion — **18/18 assets, 18/18 unique checks, 14 jobs, 7 schedules, 1 sensor**.
- `.venv/bin/sqlmesh --paths transforms/main lint` — passed.
- `cd transforms/main && ../../.venv/bin/sqlmesh test` — **13 passed** against DuckDB fixtures.
- Static Soda structure validation — **25 contracts valid** with required `dataset` and `columns` keys.
- `scripts/generate_docs.py --check` — **20 files in sync**.
- Staging and platform-health generation checks — passed.
- Ruff check/format and focused MyPy — passed for implementation/tests.
- `git diff --check` and empty staging — passed.
- Shared warehouse SHA-256 remained
  `3f7ad93d93682d5012496599cdcab94b07526aa2b70e8d1ec7982f6ff55f25e4`.
- AVONET manifest SHA-256 remained
  `2995f2e8a37caa7ca2014bdc1acbd75d2b8a7a7067c89a380a8c910a3ad3bf97`.

## What this supports

This supports the ticket's exact 14→18 check repair while preserving models,
assets, contracts, raw policy, jobs, schedules, sensors, source behavior, and
protected state. No contract, model, CDM, source, job, schedule, sensor, or
freshness definition changed.

## Limits

Checks were resolved but not executed. No Soda verification against the shared
warehouse, SQLMesh plan/apply, source refresh, provider request, asset
materialization, warehouse query/write, stage, commit, or push occurred.
