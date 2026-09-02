# ADR-0008: Polaris Iceberg raw authority

**Status:** Accepted · 2026-09 · supersedes ADR-0007

## Context

Quack enabled concurrent dlt clients to share one local DuckDB file, but required
append-only workarounds, post-load deduplication, transient metadata views, and a
single server lifecycle. Raw data also remained bound to one local database.
Databox now requires durable Iceberg snapshots in S3 while retaining local
DuckDB and SQLMesh consumers without always-on infrastructure.

## Decision

dlt-managed Iceberg tables in AWS S3 are authoritative for raw source data.
Apache Polaris is the sole active Iceberg catalog; its service and PostgreSQL
metadata backend run locally through `compose.iceberg.yml`.

- dlt writes each `raw_<source>` dataset through its Iceberg filesystem
  destination and commits table metadata through Polaris.
- Every successful source load publishes explicit `_dlt_load_status` metadata.
- The registry declares Iceberg authority and the attached analytics catalog.
- The shared refresh validates Polaris and S3 configuration, runs eligible
  Dagster source jobs concurrently, inspects authoritative tables/load status,
  and invokes native SQLMesh only after all ingestion succeeds.
- DuckDB remains the local SQLMesh transformation, application-state, and product
  serving database; it reads raw tables through the attached Polaris catalog.
- AVONET remains an independent validated replacement; USFWS remains
  explicit-target-only.
- Quack is not part of the primary ingestion or refresh path.

## Consequences

**Positive:**

- Raw data and Iceberg metadata files are durable in S3.
- Iceberg provides merge/replacement snapshots without Quack-specific cleanup.
- Polaris gives every local client one logical table registry.
- Concurrent sources no longer compete for one DuckDB writer.

**Negative:**

- Local Polaris PostgreSQL contains catalog authority and must be preserved or
  backed up; S3 files alone are not a complete catalog recovery strategy.
- Refresh requires Polaris, S3, and writer credentials.
- Off-machine consumers cannot use the local catalog. Public Rufous production
  remains paused until its release path is separately designed.

**Neutral:**

- Local DuckDB and native SQLMesh planning remain in place.
- No always-on remote catalog is introduced.
