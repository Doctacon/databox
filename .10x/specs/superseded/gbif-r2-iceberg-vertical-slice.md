Status: superseded
Created: 2026-08-31
Updated: 2026-09-03

# GBIF Iceberg vertical slice

Superseded when the R2 compatibility path was retired; GBIF now publishes to
the Polaris-governed AWS S3 warehouse.

## Purpose and scope

This specification governs a reversible proof that the existing GBIF source can be loaded through dlt/PyIceberg into a Polaris-governed Iceberg table in Cloudflare R2, read through DuckDB, transformed by SQLMesh into local DuckDB, and consumed by existing local Rufous FastAPI behavior.

The governing platform decision is `.10x/decisions/superseded/local-rufous-polaris-r2-iceberg-architecture.md`. Technical uncertainties and proof gates are recorded in `.10x/research/2026-08-31-polaris-r2-iceberg-compatibility.md`.

## Required behavior

### Compatibility gate

Before the production GBIF path changes, a bounded smoke table MUST prove all of the following with pinned or exactly recorded versions:

1. Polaris uses PostgreSQL persistence and survives a normal Compose restart.
2. Polaris creates and resolves a catalog backed by the dedicated R2 bucket with STS credential vending disabled.
3. PyIceberg creates a namespace/table, commits data, reloads it, and performs a repeat-run keyed merge through Polaris using the shared bucket-scoped lake credentials.
4. DuckDB attaches the same catalog, reads the committed rows, performs one bounded catalog-managed write, and observes the resulting snapshot.
5. No operation touches existing Databox R2 objects, local warehouse tables, or production GBIF tables.

Failure of any gate MUST leave the migration blocked. The implementation MUST NOT substitute another catalog, unsafe metadata guessing, a managed proprietary catalog, or an unreviewed transformation engine.

### Parallel GBIF migration

- The existing `raw_gbif.occurrences` DuckDB path MUST remain available throughout validation.
- The lake path MUST use a separate validation namespace until parity is accepted.
- GBIF source fields, primary key `key`, merge semantics, query boundaries, attribution, and existing record cap MUST remain unchanged.
- Validation SHOULD compare outputs from the same bounded extracted fixture or captured input. It MUST NOT claim exact parity from separate live GBIF requests whose results may change between calls.
- The existing local DuckDB GBIF path MUST NOT be deleted during this slice.

### Transformation and application path

- DuckDB MUST read the GBIF Iceberg source through Polaris.
- SQLMesh MUST continue to materialize `gbif_occurrence_evidence` into local DuckDB for this slice.
- Existing FastAPI response contracts and Rufous product behavior MUST remain unchanged except for the specified bounded unavailable behavior when Polaris is unavailable.
- Rufous MUST NOT query Polaris or R2 directly from React.

### Parity

Parity evidence MUST cover:

- source row count for the bounded common input;
- primary-key set equality;
- column names and compatible value/null behavior used by `gbif_occurrence_evidence`;
- transformed model row count and business-key equality;
- at least one existing FastAPI/Rufous request whose result depends on GBIF evidence;
- repeat-run merge/idempotency behavior;
- Compose restart durability;
- rollback to the preserved local GBIF source path.

Differences caused by an explicitly documented physical type representation MAY be accepted only if transformed values and API behavior are equivalent and the active source/model contracts remain satisfied.

## Failure behavior

- Missing Polaris, PostgreSQL, R2, catalog, namespace, table, or credentials MUST fail explicitly.
- The system MUST NOT silently fall back during parity execution because fallback would invalidate evidence about the selected path.
- Existing local GBIF remains the operator-controlled rollback path, not an automatic hidden fallback.
- Errors exposed to Rufous MUST be user-friendly and secret-free; diagnostic detail remains server-side.

## Acceptance criteria

- Every compatibility gate has reproducible evidence.
- The dedicated R2 bucket and validation namespace are the only cloud storage locations touched.
- The GBIF Iceberg table is cataloged only by Polaris.
- DuckDB reads the table through Polaris without metadata guessing.
- SQLMesh produces the existing local transformed model from the Iceberg source.
- Defined parity checks pass on a common bounded input.
- A local Rufous request using GBIF evidence remains behaviorally compatible.
- Stopping Polaris produces the specified unavailable behavior.
- The existing DuckDB GBIF path remains intact and rollback is demonstrated.

## Explicit exclusions

- Removing GBIF
- Adding or changing direct eBird API product behavior
- Migrating another source
- Materializing SQLMesh outputs as Iceberg
- Replacing SQLMesh with dbt
- Containerizing Dagster, FastAPI, SQLMesh, or Vite
- Moving Dagster or SQLMesh state into PostgreSQL
- Public Rufous changes
- Bulk production backfill or deletion of old data
