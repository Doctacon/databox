Status: active
Created: 2026-08-31
Updated: 2026-08-31

# Local Iceberg Databox platform

## Purpose and scope

This specification replaces `.10x/specs/superseded/local-only-databox-platform.md`. It governs the platform boundary for a local Rufous application that reads selected source data from an R2-backed Iceberg lake through Apache Polaris while retaining local DuckDB for application state and selected transformed models.

It does not require every source or transformed model to migrate to Iceberg.

## Platform contract

- Rufous MUST remain a local React application using the local FastAPI API.
- Browser code MUST NOT connect directly to DuckDB, Polaris, PostgreSQL, R2, or provider APIs requiring secrets.
- Polaris MUST be the sole catalog authority for lake Iceberg tables.
- Iceberg data and metadata MUST reside only within a dedicated Databox R2 bucket and configured warehouse prefix.
- Polaris catalog state MUST use PostgreSQL persistence.
- Polaris and PostgreSQL MUST run through Docker Compose with pinned image versions.
- PostgreSQL MUST use a durable named volume. Ordinary `docker compose down` MUST preserve the volume.
- No routine command may automatically purge the Polaris catalog, PostgreSQL volume, or R2 objects.
- Destructive cleanup MUST be explicit, narrowly scoped, and documented separately from ordinary shutdown.
- Polaris authentication MUST remain enabled. Secrets MUST come from ignored environment configuration and placeholders only may be committed.
- R2 credential vending through AWS STS MUST NOT be assumed. PyIceberg and DuckDB MUST use the shared direct, bucket-scoped server-side lake credential pair when the catalog has `stsUnavailable` enabled.
- FastAPI MUST return a bounded, user-friendly unavailable response when a required catalog or lake dependency cannot be reached. It MUST NOT expose credentials, endpoints containing secrets, stack traces, or raw upstream responses.

## Transitional storage contract

- Non-migrated sources MUST continue to obey `.10x/specs/parallel-quack-local-refresh.md` and use the existing local DuckDB path.
- Migrated lake sources MUST write through PyIceberg to Polaris and MUST NOT also treat a filesystem, SQLite, SQL, or in-memory catalog as authoritative.
- DuckDB MUST resolve managed lake tables through Polaris rather than unsafe metadata-version guessing.
- SQLMesh MAY read attached Iceberg tables and materialize application-owned outputs into local DuckDB.
- Moving transformed models to Iceberg requires separate evidence and ratification.

## Persistence and recovery

- R2 objects and Polaris PostgreSQL state MUST be treated as a coordinated durable system.
- Restarting or recreating a Polaris container MUST preserve catalog identity through PostgreSQL.
- A missing PostgreSQL volume MUST NOT trigger automatic catalog recreation against existing R2 prefixes.
- Readiness checks MUST distinguish catalog unavailability from missing credentials and missing tables without exposing secrets.
- Backup, restore, purge, orphan-file cleanup, and disaster recovery are excluded from the first slice and MUST NOT be implied by ordinary Compose lifecycle commands.

## Acceptance scenarios

### Restart durability

Given a catalog and table created through Polaris, when Compose is stopped normally and restarted, then the catalog resolves the same table and the table remains readable.

### Catalog unavailable

Given Polaris is stopped, when local Rufous requests lake-backed data, then FastAPI returns a bounded unavailable response and does not silently use stale or guessed Iceberg metadata.

### Credential boundary

Given the local React bundle and API response surface, when they are inspected, then no Polaris, PostgreSQL, R2, provider, or model credential is present.

### Transitional source

Given one migrated source and one non-migrated source, when the local transformation runs, then DuckDB can read both through their governed paths without changing the non-migrated source's Quack contract.

## Explicit exclusions

- Public Rufous deployment changes
- Dagster containerization
- Dagster or SQLMesh state migration to PostgreSQL
- Automatic failover or offline lake snapshots
- Migration of every source
- Direct SQLMesh materialization into Iceberg
- Catalog or object-store deletion automation
