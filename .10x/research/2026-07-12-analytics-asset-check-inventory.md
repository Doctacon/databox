Status: done
Created: 2026-07-12
Updated: 2026-07-12

# Analytics asset and Soda check inventory

## Question

Do the manual SQLMesh/Soda model lists in
`packages/databox/databox/orchestration/domains/analytics.py` match current
SQLMesh models, CDM tables, Soda contracts, and resolved Dagster assets/checks?

## Sources and methods

Inspected:

- `packages/databox/databox/orchestration/domains/analytics.py`;
- `packages/databox/databox/orchestration/definitions.py` and `_factories.py`;
- all 18 `transforms/main/models/**/*.sql` declarations via SQLMesh dialect
  parsing;
- `.schema/environmental_observations/CDM.dbml`;
- all 25 `soda/contracts/**/*.yaml` dataset declarations;
- generated `docs/dictionary/` inventory;
- resolved Dagster `AssetSpec` and `AssetCheckSpec` inventories from `defs`;
- active contracts/observability docs and source-domain check exports.

Definition loading was metadata-only. No assets/checks/jobs were executed. Shared
warehouse and AVONET manifest fingerprints were captured before and verified
byte-identical afterward.

## Findings

### Exact modeled inventory

SQLMesh declares 18 models. All 18 resolve as Dagster SQLMesh assets, all 18
have Soda contracts, and all 18 appear in the generated dictionary. Only 14
resolve with the `soda_contract` Dagster asset check.

| SQLMesh model | CDM table | Contract | Asset | Soda check |
| --- | --- | --- | --- | --- |
| `analytics.platform_health` | no | yes | yes | yes |
| `birding_agent.arizona_species_catalog` | yes | yes | yes | **no** |
| `birding_agent.gbif_occurrence_evidence` | no | yes | yes | yes |
| `birding_agent.recent_observation_evidence` | no | yes | yes | yes |
| `birding_agent.species_lookup` | no | yes | yes | yes |
| `birding_agent.xeno_canto_media_evidence` | no | yes | yes | yes |
| `environmental_observations.dim_bird_hotspot` | yes | yes | yes | yes |
| `environmental_observations.dim_bird_species_traits` | yes | yes | yes | **no** |
| `environmental_observations.dim_species` | yes | yes | yes | yes |
| `environmental_observations.dim_streamgage_site` | yes | yes | yes | yes |
| `environmental_observations.dim_weather_station` | yes | yes | yes | yes |
| `environmental_observations.fact_bird_observation` | yes | yes | yes | yes |
| `environmental_observations.fact_bird_occurrence` | yes | yes | yes | **no** |
| `environmental_observations.fact_bird_sound_recording` | yes | yes | yes | **no** |
| `environmental_observations.fact_earthquake_event` | yes | yes | yes | yes |
| `environmental_observations.fact_region_daily_stats` | yes | yes | yes | yes |
| `environmental_observations.fact_streamflow_observation` | yes | yes | yes | yes |
| `environmental_observations.fact_weather_observation` | yes | yes | yes | yes |

### Manual-list drift

`analytics.py` manually declares the same 14 names that currently receive
checks. It omits exactly four later models:

- `birding_agent.arizona_species_catalog`;
- `environmental_observations.dim_bird_species_traits`;
- `environmental_observations.fact_bird_occurrence`;
- `environmental_observations.fact_bird_sound_recording`.

There are no extra/stale manual names. The exported `sqlmesh_asset_keys` list is
not consumed outside `analytics.py`; actual assets come from the SQLMesh
multi-asset and already include all 18 models. Therefore:

- **missing assets:** none;
- **missing checks:** four, significant correctness drift;
- **duplicate authority:** the two manual model-name lists control check
  creation and can drift from the SQLMesh project and contracts.

### CDM and non-CDM classification

CDM DBML declares 13 tables: 12 environmental-observations tables plus
`birding_agent.arizona_species_catalog`. The remaining five SQLMesh models are
intentional non-CDM interfaces/operations:

- four planner-facing `birding_agent` evidence/lookup models;
- `analytics.platform_health`.

All five have contracts, resolved assets, dictionary pages, and (except the CDM
catalog omission above) existing checks. Their absence from CDM DBML is
intentional, not drift.

### Raw contracts

Seven additional Soda files cover raw eBird/NOAA datasets. They are not SQLMesh
model outputs and do not resolve as checks. This matches `docs/contracts.md`,
which promises runtime Dagster checks for SQLMesh-owned datasets; raw contracts
remain structural/schema-gate authorities. No raw-check repair is recommended
under this ticket.

### Resolved orchestration baseline

Definition loading resolved:

- 18 modeled SQLMesh assets plus external raw dependencies;
- 14 SQLMesh Soda checks;
- 14 explicit jobs;
- seven schedules;
- one sensor.

The repair must change only modeled Soda check coverage from 14 to 18. Asset,
job, schedule, sensor, source, and raw-contract inventories must remain stable.

## Conclusion

Repair is required. The four missing runtime checks contradict the repository's
contract that every SQLMesh-owned dataset with a Soda contract is verified after
materialization. The gap is caused by duplicate manual name lists, not missing
models, contracts, assets, CDM artifacts, or dictionary generation.

Recommended implementation: derive `analytics.sqlmesh_asset_keys` from the 18
`sqlmesh_project.specs`, derive one Soda check per resolved SQLMesh model using
its schema/model contract path, and fail definition loading when a contract is
missing or mismatched. Delete the manual `_CDM_MODELS` and
`_BIRDING_AGENT_MODELS` lists. This reuses existing SQLMesh assets and Soda
contracts rather than creating a third inventory.

The focused implementation owner is
`.10x/tickets/done/2026-07-12-derive-soda-checks-from-sqlmesh-assets.md`.

## Limits

- Checks were resolved but not executed against warehouse data.
- No SQLMesh apply/plan, provider, refresh, asset materialization, or Soda
  verification ran.
- Definition loading emitted normal adapter-construction metadata only; the
  shared warehouse remained byte-identical.
