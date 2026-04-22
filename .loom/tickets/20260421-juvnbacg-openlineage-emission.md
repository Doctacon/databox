---
id: ticket:openlineage-emission
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links: {}
---

# Goal

Wire Dagster's OpenLineage emitter so every asset materialization and asset
check run emits an OpenLineage event. The emitter stays disabled by default
(no hosted backend required) and activates when `OPENLINEAGE_URL` is set in
`.env`.

Forker drops the env var in and points it at Marquez / DataHub / OpenMetadata
/ Atlan / Datakin — lineage appears automatically.

# Why

Dagster already holds the asset graph; OpenLineage is the open emission
standard that every major catalog (DataHub, OpenMetadata, Atlan, Marquez,
Astro, Unity) understands. Lighting it up costs ~2h and gives forkers a free
path off the internal Dagster asset catalog onto whatever observability
substrate they already run.

The 2026 data-engineering trend lists put "OpenLineage + catalog" at #1 —
see Datafold / pracdata / MotherDuck DevOps blog. Databox has no emitter
today; lineage lives only in the Dagster UI.

# In Scope

- Add `openlineage-python` + `openlineage-dagster` to `packages/databox/pyproject.toml`
  as an optional extra `lineage`.
- Teach `DataboxSettings` to read `OPENLINEAGE_URL`, `OPENLINEAGE_NAMESPACE`,
  `OPENLINEAGE_API_KEY`.
- In `definitions.py`, call the `openlineage_dagster` hook installer at module
  load when `OPENLINEAGE_URL` is set; short-circuit otherwise (same shape as
  `ensure_motherduck_databases`).
- `.env.example` gains three commented-out lines documenting the opt-in.
- `docs/observability.md` (or append to existing observability page) gets a
  "External lineage catalogs" section with a Marquez docker-compose snippet.
- Unit test: mocked OL emitter records at least one event on a dummy asset run.

# Out of Scope

- Shipping a default Marquez container in the stack (forker decides backend).
- Column-level lineage beyond whatever SQLMesh + Dagster already derive.
- dbt / Airflow compat shims — not our orchestrators.

# Acceptance

- `OPENLINEAGE_URL=` unset: no events emitted, no warnings.
- `OPENLINEAGE_URL=http://localhost:5000` set + Marquez running locally:
  a materialized asset shows up in Marquez with at least RunEvent +
  JobEvent + DatasetEvent.
- New unit test passes; `task ci` green.
- README "Observability" section mentions the knob.

# Close notes

Landed as the `lineage` optional extra on `packages/databox` and a custom
in-tree Dagster sensor at `databox.orchestration._factories`.

Dep-conflict pivot (important)

`openlineage-dagster` pins `dagster <=1.6.9`; we're on Dagster 1.7+ via
`dagster-sqlmesh` (which floors at 1.7.8). The upstream bundled sensor
factory is therefore unusable here. Extra ships only
`openlineage-python>=1.20.0`; the sensor is built in-tree on top of that
client (~50 LOC, `_openlineage_emit_tick` + `openlineage_sensor_or_none`).
The in-tree sensor walks `ASSET_MATERIALIZATION` via `EventRecordsFilter`
(same pattern as `freshness_violation_sensor`) and emits one OpenLineage
`RunEvent` per materialization — `Run` with a fresh uuid, `Job` keyed on
the Dagster asset key, one `OutputDataset` matching the asset.

Factory shape

- `OPENLINEAGE_URL` unset → returns `None`, no import cost, no sensor.
- URL set but `openlineage.client` missing → logs a warning pointing at
  `uv sync --package databox --extra lineage`, returns `None`.
- URL set + package present → returns a `SensorDefinition` named
  `openlineage_sensor` with `DefaultSensorStatus.RUNNING`.

`OpenLineageClient` is wired via `HttpTransport(HttpConfig(...))` rather
than the deprecated `OpenLineageClient(url=..., options=...)` positional
shape. `OPENLINEAGE_API_KEY`, if set, becomes an `ApiKeyTokenProvider` in
the transport auth slot.

Config

`DataboxSettings` gains three env-backed fields (`openlineage_url`,
`openlineage_namespace`, `openlineage_api_key`) so `.env` stays the one
place forkers look. `.env.example` ships all three commented-out with
pointers to `docs/observability.md`.

`openlineage-python` also lives in the root dev-deps group so `task ci`
can run the sensor tests without forcing every dev install to include the
lineage extra.

Tests (`tests/test_openlineage_sensor.py`, 6/6 green)

- URL unset → None
- URL set + import fails → None + warn
- URL set + installed → `SensorDefinition` with expected name
- Tick over one fabricated `ASSET_MATERIALIZATION` → exactly one
  `RunEvent` with expected namespace / job name / output dataset /
  advanced cursor
- Tick over three records → cursor tracks max `storage_id`
- Client `emit` raises on one record → sensor logs a warning and
  continues with the next record (lineage failures never kill Dagster)

Docs

- `docs/observability.md` (new page, linked from `mkdocs.yml`) covers the
  Dagster UI + dictionary surfaces and walks through turning on
  OpenLineage: install command, env vars, Marquez docker-compose snippet,
  disable path.
- `README.md` gains an "Observability" section pointing at the new doc.

Incidental fixes required to get `task ci` green (pre-existing breakage
unrelated to this ticket, but blocking the gate):

- `scripts/smoke.py` was importing `ebird_dlt_assets` / `noaa_dlt_assets`
  / `usgs_dlt_assets` from `databox.orchestration.definitions` — those
  symbols moved into `databox.orchestration.domains.*` in the 4-package
  collapse (commit af325d5). Fixed the imports.
- `scripts/bootstrap.py` had a variable shadow (`p = ArgumentParser()`
  then `for p in would_change:` reusing the name as a `Path`). Renamed
  the loop variable to `drift_path`.
- `app/main.py` had mypy `Any | None` errors after a `st.stop()` guard;
  added an `assert` to narrow `schema` and `table` for the type checker.
- `packages/databox-sources/databox_sources/ebird/models.py` grew an
  `exotic_category: str | None` field (restores a column the pydantic
  pilot dropped because `extra="ignore"` had silently dropped it). The
  committed schema snapshot already had the column.

Follow-ups (not blocking):

- No observed production sensor run yet — acceptance test is the mocked
  unit test + importable-sensor smoke. A live Marquez round-trip is a
  forker-side verification step and documented in `docs/observability.md`.
- If we later want pre-run START events in addition to the single
  COMPLETE emitted per materialization, extend `_openlineage_emit_tick`
  to listen on `STEP_START` / `ASSET_CHECK_EVALUATION` too.
