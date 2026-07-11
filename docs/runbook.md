# Operations runbook

Finite validation commands only; `task dagster:dev` starts a long-running UI and
must be stopped with Ctrl-C.

## Rebuild local warehouse from sources

```bash
task db:reset
task full-refresh
```

`task full-refresh` starts one Quack server, launches every source marked
`parallel_refresh=True` concurrently as an independent Dagster job, waits for
all jobs, stops
and deduplicates the warehouse, then invokes native SQLMesh only if every source
succeeded. `SOURCE_START`/`SOURCE_END` lines and Dagster run IDs attribute the
interleaved logs; overlap is calculated from cross-process timestamps around
each actual dlt/Quack ingest session, not process startup time. The command also
prints core raw row counts and requires `main_dlt_relations=0` before SQLMesh.
The expected local layout is one `data/databox.duckdb` with raw schemas plus
SQLMesh schemas such as `environmental_observations` and `analytics`.

Static pinned AVONET is deliberately not part of this six-source refresh. Run
its independent `avonet_ingest` Dagster job explicitly when a validated
`raw_avonet.species_traits` bootstrap is required; it has no recurring schedule.
The job clears crash residue, append-loads Quack-owned `raw_avonet_staging`,
stops Quack, then validates and atomically publishes the complete final snapshot
in one single-writer transaction. Failures preserve the prior final snapshot and
remove staging best-effort; generic raw dedupe is not used for AVONET.

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

## Trip-plan calendar invitations

Trip invitations are created only by a confirmed `POST` to
`/api/trip-plans/{plan_id}/calendar-invite?confirm=true`. Plan creation,
application startup, replay, and all `GET` routes are status-only and never send.
The action reuses the server-only `BIRD_ALERT_SMTP_*` loopback STARTTLS settings;
no recipient or transport value is returned by the API.

Apply `migrations/20260711_trip_plan_calendar.sql` for an offline migration. The
same additive DDL is applied idempotently by the first explicit invite mutation.
Trip tables use only `trip_plan_id`; they never fabricate watch, species, or
activation-generation relationships.

An `accepted` status means **Accepted by local mail bridge**, not confirmed inbox
or calendar delivery. A `delivery_unknown` row must be reconciled explicitly with
mark-delivered or mark-not-delivered-and-retry. Never resend it automatically.
Failed retries and not-delivered reconciliation atomically supersede the old row,
regenerate the canonical plan with the stable UID and a greater sequence, and immediately
claim/send the replacement through the confirmed reconciliation API. Transient rows are
scheduled at 1, 5, and 15 minutes; an operator or local worker must invoke confirmed
`POST /api/trip-calendar-deliveries/deliver-due?confirm=true` at or after `next_attempt_at`
to claim and send one due row. This endpoint never claims `delivery_unknown`; those rows
remain manual-reconciliation-only. Resolved non-current rows may be cleaned after 90 days;
the current intent/action and unresolved unknown rows are retained.

Feature verification must use an injected fake SMTP transport. The prior bounded
live Bridge authorization is exhausted; do not run another live verification
without a new explicit authorization.
