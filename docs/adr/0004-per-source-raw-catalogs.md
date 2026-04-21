# ADR-0004: Per-source raw DuckDB catalogs

**Status:** Accepted · 2026-03

## Context

dlt writes ingested records into a landing zone. Early versions used a
single catalog (`data/databox.duckdb`) with per-source schemas
(`raw_ebird.*`, `raw_noaa.*`, `raw_usgs.*`). This worked for correctness
but serialized all loads:

- DuckDB holds a file-level lock for writes. Concurrent pipelines
  blocked each other.
- A failed load partially touched the same file that downstream
  transforms were about to read.
- The transform-side DuckDB file grew large, and checkpoint/rollback
  semantics interacted awkwardly with dlt's own staging commit.

## Decision

Split raw storage into **per-source DuckDB files**:

```
data/raw_ebird.duckdb
data/raw_noaa.duckdb
data/raw_usgs.duckdb
data/databox.duckdb   # transform output catalog only
```

`settings.raw_<source>_path` returns the source-specific path for both
local and MotherDuck backends. SQLMesh staging models `ATTACH` each raw
file read-only as needed.

## Consequences

**Positive:**
- dlt pipelines run in parallel without lock contention. The full
  refresh time drops substantially when multiple sources ingest together.
- A bad ingest for one source cannot corrupt another source's raw data.
- Each source's raw file can be deleted/rebuilt independently during
  debugging.
- The transform catalog stays small — it holds only modeled data.

**Negative:**
- Multiple files to back up / sync to MotherDuck instead of one.
- SQL that crosses raw sources must `ATTACH` all relevant files, which
  is slightly more verbose than referencing shared schemas.
- `list_databases` / `list_tables` tooling needs to know where to look,
  not just open one file.

**Neutral:**
- On MotherDuck, "files" become "databases" in the same account, so the
  per-source split carries over naturally without the filesystem-level
  lock concern (MotherDuck handles that internally).
