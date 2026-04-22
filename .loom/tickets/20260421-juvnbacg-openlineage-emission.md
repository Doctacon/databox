---
id: ticket:openlineage-emission
kind: ticket
status: ready
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
