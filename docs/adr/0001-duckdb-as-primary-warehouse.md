# ADR-0001: DuckDB as the primary warehouse

**Status:** Accepted · 2026-02 · reaffirmed 2026-04 when MotherDuck cloud
path was added (see ADR-0006).

## Context

Databox is a single-operator data platform. Three hard constraints shape
every infrastructure choice:

1. **Zero fixed cost.** No always-on database instance, no managed
   warehouse contract, no per-seat BI licensing.
2. **Zero-infra local mode.** A new contributor (or a future me on a new
   laptop) should be productive in minutes, not after provisioning
   anything.
3. **Analytical workload profile.** The data is batch-ingested daily,
   modeled with SQL, and queried by a handful of dashboards. No OLTP, no
   high concurrency, no real-time writes.

Candidate stacks considered: Postgres + dbt, Snowflake (free tier),
BigQuery (free tier), ClickHouse, DuckDB, Parquet-on-S3 + Athena.

## Decision

Use DuckDB as the primary warehouse. All transformations run against
DuckDB; all marts live in DuckDB files under `data/`.

## Consequences

**Positive:**
- Zero infra. The database is a `.duckdb` file on disk.
- Analytical queries against the flagship mart finish in tens of
  milliseconds locally. No tuning, no clustering keys.
- Columnar storage + vectorized execution make this genuinely fast for
  the workload, not just "fine for small data".
- First-class Parquet, JSON, and HTTP extensions mean dlt and downstream
  consumers can read/write a wide variety of formats without glue code.
- Open source (MIT). No vendor lock-in.

**Negative:**
- No concurrent writes. Not an issue at single-operator scale; would be a
  real problem at team scale.
- No row-level security, no fine-grained access control. Out of scope
  for this project; would be disqualifying at enterprise scale.
- The `.duckdb` file is binary and doesn't diff cleanly — source of
  truth is always the raw ingest + transform code, never the database
  file itself.

**Neutral:**
- The cloud path is handled by MotherDuck (see ADR-0006), which accepts
  the same DuckDB SQL. That keeps the local/cloud gap thin.
