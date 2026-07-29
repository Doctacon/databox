Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-investigate-analytics-asset-check-inventory.md, .10x/research/2026-07-12-analytics-asset-check-inventory.md

# Analytics asset and check inventory evidence

## What was observed

Metadata resolution proves 18 SQLMesh model outputs, 18 modeled Soda contracts,
18 resolved SQLMesh assets, and only 14 resolved Soda checks. Missing checks are
exactly:

- `birding_agent.arizona_species_catalog`;
- `environmental_observations.dim_bird_species_traits`;
- `environmental_observations.fact_bird_occurrence`;
- `environmental_observations.fact_bird_sound_recording`.

No SQLMesh asset is missing. Seven raw contracts are intentionally outside the
SQLMesh-owned runtime-check contract.

## Procedure

- Enumerated model/contract/CDM/dictionary files with `find` and `rg`.
- Parsed all SQLMesh `MODEL` declarations using `sqlmesh.core.dialect.parse`.
- Parsed Soda `dataset` declarations with safe YAML loading.
- Imported `analytics` and `defs`, then inspected
  `resolve_all_asset_specs()` and each `AssetChecksDefinition.check_specs`.
- Inspected explicit job/schedule/sensor names.
- Compared all sets in `/tmp/analytics-inventory.json`.
- Fingerprinted protected files before/after metadata loading.

## Results

- Models: 18.
- Modeled contracts: 18/18; all contract dataset identities match model names.
- Generated dictionary model pages: 18/18.
- CDM tables: 13; five non-CDM planner/operational models classified as
  intentional.
- Resolved modeled assets: 18/18.
- Resolved Soda checks: 14/18.
- Missing checks: four; extra checks: zero.
- Explicit jobs: 14; schedules: seven; sensors: one.
- Shared warehouse SHA-256 before/after:
  `3f7ad93d93682d5012496599cdcab94b07526aa2b70e8d1ec7982f6ff55f25e4`.
- AVONET manifest SHA-256 before/after:
  `2995f2e8a37caa7ca2014bdc1acbd75d2b8a7a7067c89a380a8c910a3ad3bf97`.
- `git diff --check`: passed.
- `git diff --cached --name-only`: empty.

## What this supports

This supports opening a repair ticket with exact before/after semantics: preserve
18 assets and all orchestration inventories while increasing modeled Soda check
coverage from 14 to 18 and removing duplicate manual model-name authority.

## Limits

This is metadata evidence. No check or asset was executed, and no warehouse data
quality claim is made. No provider, refresh, SQLMesh apply/plan, materialization,
shared-warehouse query/write, stage, commit, or push occurred.
