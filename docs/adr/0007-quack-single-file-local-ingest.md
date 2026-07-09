# ADR-0007: Quack single-file local ingest

**Status:** Accepted · 2026-07 · amended 2026-07 for the local-only platform

## Context

ADR-0004 split raw dlt landing storage into one DuckDB file per source because
DuckDB's native file format allows only one writer process. That layout made
parallel ingest possible but weakened the single composable warehouse model.

Quack provides client-server access to DuckDB: one server process owns the
file while clients write through the `quack:` protocol.

## Decision

Quack is the only supported dlt write path, and `data/databox.duckdb` is the
only supported warehouse and application-state database.

- Every source writes to a physical `raw_<source>` schema in that file.
- Independent source jobs own a Quack server lifecycle when launched alone.
- Full refresh starts exactly one Quack server, launches every registered source
  as an independent concurrent Dagster job/client, waits for all clients, then
  stops the server.
- Transient `main._dlt_*` union views expose every source's physical metadata
  tables during repeat loads without allowing concurrent clients to overwrite a
  source-specific global view. The views are removed when the server stops.
- dlt writes append-only physical tables because Quack's attached-catalog path
  does not support every DELETE statement emitted for merge loads.
- After the server stops, Databox deduplicates known raw tables by their
  declared primary keys.
- SQLMesh runs only after every required source job succeeds.
- SQLMesh uses only its local gateway and reads source schemas from the shared
  warehouse.

## Consequences

**Positive:**

- Raw data, transformed models, and local application state share one portable
  DuckDB file.
- dlt writes go through Quack rather than direct competing file connections.
- Adding a source adds a raw schema rather than another database file or
  backend configuration branch.
- Runtime settings, SQLMesh, dlt, Dagster, and operational docs have one local
  storage path.

**Negative:**

- Quack remains beta, so the destination helper requires DuckDB session setup
  SQL and a post-load deduplication step.
- Concurrent clients make source logs interleave; source-prefixed start/end
  markers and independent Dagster run IDs provide attribution.
