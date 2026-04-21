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

Retire the Typer CLI. **Dagster is the single entrypoint** for every
non-trivial operation: ingestion, transformation, quality checks,
schedules, sensors, backfills. A thin `Taskfile.yml` wraps the common
Dagster commands (`task dagster:dev`, `task dagster:materialize`,
`task full-refresh`) for ergonomic reasons but does not implement any
logic of its own.

## Consequences

**Positive:**
- One mental model. New contributors learn Dagster assets and see
  every pipeline step as a node in one graph.
- Native lineage across dlt → SQLMesh → Soda. The UI shows that
  `analytics.fct_species_environment_daily` depends on
  `noaa.int_weather_by_h3_day` which depends on `raw_noaa.daily_weather`,
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
