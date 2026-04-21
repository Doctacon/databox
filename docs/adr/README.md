# Architecture Decision Records

Backfilled ADRs for the load-bearing architectural choices in this repo.
Each ADR follows [Michael Nygard's
format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):
**Context**, **Decision**, **Consequences**, **Status**.

Numbered in order of decision, not importance. A decision that turned out
to be wrong would be marked **Superseded** and keep its number.

| ID | Title | Status |
|---|---|---|
| [ADR-0001](0001-duckdb-as-primary-warehouse.md) | DuckDB as the primary warehouse | Accepted |
| [ADR-0002](0002-sqlmesh-over-dbt.md) | SQLMesh over dbt | Accepted |
| [ADR-0003](0003-single-sqlmesh-project.md) | Single SQLMesh project across all sources | Accepted |
| [ADR-0004](0004-per-source-raw-catalogs.md) | Per-source raw DuckDB catalogs | Accepted |
| [ADR-0005](0005-dagster-as-sole-orchestrator.md) | Dagster as the sole orchestrator | Accepted |
| [ADR-0006](0006-motherduck-as-cloud-path.md) | MotherDuck as the cloud path | Accepted |
