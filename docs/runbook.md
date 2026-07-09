# Operations runbook

Finite validation commands only; `task dagster:dev` starts a long-running UI and
must be stopped with Ctrl-C.

## Rebuild local warehouse from sources

```bash
task db:reset
task full-refresh
```

`task full-refresh` starts one Quack server, launches every registered dlt
source concurrently as an independent Dagster job, waits for all jobs, stops
and deduplicates the warehouse, then invokes native SQLMesh only if every source
succeeded. `SOURCE_START`/`SOURCE_END` lines and Dagster run IDs attribute the
interleaved logs; overlap is calculated from cross-process timestamps around
each actual dlt/Quack ingest session, not process startup time. The command also
prints core raw row counts and requires `main_dlt_relations=0` before SQLMesh.
The expected local layout is one `data/databox.duckdb` with raw schemas plus
SQLMesh schemas such as `environmental_observations` and `analytics`.

## Smoke verification

```bash
task verify
cd transforms/main && ../../.venv/bin/sqlmesh test
```

`task verify` uses `DATABOX_SMOKE=1` with the same shared-server concurrent
source path, then restates SQLMesh prod through the native CLI.

## SQLMesh dev loop

```bash
cd transforms/main
../../.venv/bin/sqlmesh plan dev --auto-apply --no-prompts
../../.venv/bin/sqlmesh test
```

Dev schemas use the `__dev` suffix, for example
`environmental_observations__dev.fact_bird_observation`.

## CDM row-count sanity checks

```sql
SELECT COUNT(*) FROM environmental_observations.fact_bird_observation;
SELECT COUNT(*) FROM environmental_observations.fact_weather_observation;
SELECT COUNT(*) FROM environmental_observations.fact_streamflow_observation;
SELECT COUNT(*) FROM environmental_observations.fact_earthquake_event;
SELECT COUNT(*) FROM analytics.platform_health;
```

Primary key duplicate checks should return zero:

```sql
SELECT COUNT(*) - COUNT(DISTINCT bird_observation_sk)
FROM environmental_observations.fact_bird_observation;

SELECT COUNT(*) - COUNT(DISTINCT weather_observation_sk)
FROM environmental_observations.fact_weather_observation;

SELECT COUNT(*) - COUNT(DISTINCT streamflow_observation_sk)
FROM environmental_observations.fact_streamflow_observation;

SELECT COUNT(*) - COUNT(DISTINCT earthquake_event_sk)
FROM environmental_observations.fact_earthquake_event;
```

## Broken local file recovery

```bash
mv data/databox.duckdb data/databox.duckdb.broken
task full-refresh
```

If the rebuild fails, restore the backup and inspect `.logs/` plus Dagster run
history under `.dagster/`.

## Rollback SQLMesh prod

SQLMesh plan history is the rollback mechanism:

```bash
cd transforms/main
../../.venv/bin/sqlmesh state list
../../.venv/bin/sqlmesh plan prod --restore-from <previous-plan-id> --auto-apply
```

## UI launch

```bash
task dagster:dev
```

This command is intentionally long-running. Stop it with Ctrl-C after manual UI
inspection.
