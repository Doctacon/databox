# ADR-0007: Quack single-file local ingest

**Status:** Accepted · 2026-07

## Context

ADR-0004 split raw dlt landing storage into one DuckDB file per source because
DuckDB's native file format allowed only one writer process. That made parallel
local ingest possible, but it weakened Databox's "one composable data stack"
shape: the local warehouse was a bundle of raw files plus one transform file.

DuckDB Quack now provides client-server access to a DuckDB database. One server
process owns the `.duckdb` file while multiple client processes can write
through the `quack:` protocol.

## Decision

Make Quack the default local ingest path.

- `DATABOX_BACKEND=quack` is the default.
- Each dlt source is a Dagster ingest asset/job. For local Quack runs, that
  source job starts a Quack server over `data/databox.duckdb`, runs exactly one
  dlt source through Quack, stops Quack, then opens the file directly.
- During the Quack load, dlt writes append-only physical tables in each
  source's `raw_<source>` schema because Quack's beta attached-catalog path does
  not yet support every DELETE statement dlt emits for merge loads.
- After the Quack server stops, Databox deduplicates known raw tables by their
  declared primary keys in place.
- `task full-refresh` runs the source ingest jobs sequentially for hermeticity,
  then invokes the native SQLMesh CLI to restate prod models from the refreshed
  raw schemas.
- SQLMesh reads raw sources using two-part names such as
  `raw_ebird.recent_observations`; under Quack those are physical tables in the
  primary `data/databox.duckdb` file, while MotherDuck and legacy local continue
  to expose the same two-part names through one raw catalog/database per source.
- The old `DATABOX_BACKEND=local` per-source-file path remains only as an escape
  hatch.

## Consequences

**Positive:**

- The local data stack is one DuckDB file again.
- dlt sources write through Quack without direct multi-process file opens.
- Each source ingest is a Dagster asset run with its own Quack lifecycle.
- Adding a source means adding another raw schema, not another local database
  file to track.

**Negative:**

- Quack is beta, so this path is intentionally pragmatic rather than polished.
- Local full refresh now has explicit per-source ingest phases before SQLMesh
  restates modeled assets.
- The dlt DuckDB destination does not yet expose first-class Quack connection
  setup, so Databox uses a small destination helper that configures Quack via
  DuckDB session setup SQL and then repairs append-only raw tables post-load.

**Neutral:**

- MotherDuck still uses one database per raw source.
- Legacy `local` still supports the ADR-0004 layout for fallback/debugging.
