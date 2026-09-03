Status: superseded
Created: 2026-09-02
Updated: 2026-09-03

# Local Rufous with a Polaris-governed AWS S3 Iceberg lake

Superseded for repository ownership by `.10x/decisions/split-rufous-into-standalone-repository.md`. Databox retains Polaris/S3 Iceberg ingestion and local DuckDB models; Rufous consumes only the versioned DuckDB product artifact.

## Context

The R2 compatibility proof was retired after Polaris credential vending proved incompatible with the intended DuckDB workflow. The GBIF vertical slice now works with Apache Polaris, AWS S3, PyIceberg, DuckDB, SQLMesh, and local FastAPI.

## Decision

- Polaris is the sole Iceberg catalog authority.
- AWS S3 is the durable Iceberg object store. Polaris assumes the configured bucket-scoped IAM role and vends temporary credentials to clients.
- `databox_lake` is the pre-provisioned shared catalog; `s3://<bucket>/warehouse/` is its warehouse.
- Migrated sources write directly to Iceberg. GBIF uses `raw_gbif.occurrences` and no longer refreshes its legacy local raw table.
- SQLMesh reads Iceberg and materializes Rufous-facing models locally in DuckDB.
- Dagster runs native ingestion functions; the targeted SQLMesh CLI refresh remains until native SQLMesh execution can be constrained without unrelated snapshot cleanup.
- Rufous remains local and FastAPI/browser clients never receive Polaris or AWS credentials.

## Consequences

AWS S3/IAM is an explicit managed-service exception to the project’s open-source-first preference. The Iceberg format, Polaris, PyIceberg, DuckDB, SQLMesh, and the client boundaries remain portable. The prior R2 decision is superseded at `.10x/decisions/superseded/local-rufous-polaris-r2-iceberg-architecture.md`.
