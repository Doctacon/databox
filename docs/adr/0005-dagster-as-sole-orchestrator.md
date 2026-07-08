# ADR-0005: Dagster as the sole orchestrator

**Status:** Accepted · 2026-03

## Context

An earlier version of this repo shipped two overlapping entrypoints: a
Typer-based `databox` CLI (`packages/databox-cli/`) and a Dagster asset
graph. The CLI exposed `databox run ebird`, `databox transform run`,
`databox quality report`, etc. Dagster exposed the same operations as
materializable assets.

That duplication was confusing. New contributors asked "which one do I
use?" and the answer was "it depends". Worse, the CLI did not have asset
lineage, retries, sensors, or scheduling — so non-trivial workflows
bypassed it anyway. The CLI was carrying maintenance cost without
buying much.

## Decision

Retire the Typer CLI. **Dagster is the single entrypoint** for dlt ingestion,
quality checks, schedules, sensors, and asset-observability workflows. A thin
`Taskfile.yml` wraps the common commands (`task dagster:dev`, source ingest
jobs, `task full-refresh`) for ergonomics.

ADR-0007 narrows this for the local Quack full-refresh path: each dlt source
still runs as a Dagster asset job, but SQLMesh transformations are invoked with
the native SQLMesh CLI after Quack shuts down so SQLMesh owns its own planning,
state, and restatement semantics directly.

## Consequences

**Positive:**
- One mental model for ingestion and quality. New contributors learn Dagster
  source assets and checks, while SQLMesh remains the direct interface for
  transform planning and restatement.
- Native lineage across dlt → SQLMesh → Soda. The UI shows that
  `environmental_observations.fact_weather_observation` depends on
  `environmental_observations.dim_weather_station` and `raw_noaa.daily_weather`,
  end to end, without extra wiring.
- Soda contracts run as Dagster **asset checks**, gating downstream
  materialization on quality automatically.
- Schedules, sensors, and partition backfills are first-class. No
  cron-on-top-of-CLI duct tape.

**Negative:**
- Dagster is a heavier dependency than Typer. It pulls in a web UI,
  gRPC, and a state store. Acceptable for this scale — not a concern
  at ~dozens of assets.
- Invoking a single asset from a terminal is slightly more ceremony
  than `databox run ebird` was. `task dagster:materialize -- asset_key`
  paves over this.

**Neutral:**
- The `task` wrapper is intentionally thin. It could be replaced with a
  Makefile or raw `dagster asset materialize` invocations without
  changing the architecture.
