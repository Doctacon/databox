---
id: ticket:motherduck-db-autocreate
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T17:05:00Z
scope:
  kind: workspace
links:
  parent: ticket:add-usgs-earthquakes-source
---

# Goal

On Dagster startup with `DATABOX_BACKEND=motherduck`, run
`CREATE DATABASE IF NOT EXISTS <db>` for every database the stack references
(`databox` + every `raw_<source>` in `DataboxSettings`).

# Why

Friction point #2 in `ticket:add-usgs-earthquakes-source`. Local DuckDB creates files
on first write; MotherDuck's ATTACH instead errors with
`"no database/share named 'raw_xxx' found"` if the database does not exist yet.
The error does not hint at `CREATE DATABASE`. A forker switching to MotherDuck
hits this on their first pipeline run.

# In Scope

- `_factories.py` (or equivalent) gains `ensure_motherduck_databases()` that:
  - no-ops when `settings.backend != "motherduck"`
  - no-ops (with a warning log) when `settings.motherduck_token` is empty
  - connects via `duckdb.connect("md:?motherduck_token=...")`
  - runs `CREATE DATABASE IF NOT EXISTS <name>` for `databox` + every `raw_*_path`
  - closes the connection
- `definitions.py` calls it at module load so Definitions evaluation triggers creation.
- Unit test: mocked duckdb connection asserts the expected DDL list is executed.

# Out of Scope

- Share-based setups (CREATE DATABASE from SHARE) — the forker uses their own.
- Managing MotherDuck users/roles/grants.
- Retrying on transient MotherDuck errors — let Dagster bubble them.

# Acceptance

- `DATABOX_BACKEND=motherduck` + missing `raw_foo` + first Definitions load does
  not fail on ATTACH; instead the CREATE runs first.
- `DATABOX_BACKEND=local` path is unchanged (function short-circuits).
- New unit test passes.

# Close Notes — 2026-04-21

Added `DataboxSettings.motherduck_database_names` — introspects `raw_*_path`
properties + prepends `databox`. Added `ensure_motherduck_databases()` in
`_factories.py`; called at module import from `definitions.py`. Short-circuits
when backend is local or token is empty. `tests/test_motherduck_autocreate.py`
covers all three branches plus introspection.

4/4 new tests green.
