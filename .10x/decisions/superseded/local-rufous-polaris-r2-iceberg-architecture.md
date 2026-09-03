Status: superseded
Created: 2026-08-31
Updated: 2026-09-03

# Local Rufous with a Polaris-governed Iceberg source lake

Superseded when Polaris credential vending proved incompatible with R2; AWS S3
became the durable object store and Rufous later moved to its own repository.

## Context

Databox currently uses one local DuckDB file for ingestion, transformed models, application state, and Rufous queries. The user wants a durable, open table-format data lake backed by a dedicated Cloudflare R2 bucket, with Apache Polaris as the authoritative Iceberg REST catalog. Rufous remains a local product accessed through its existing FastAPI boundary.

This decision supersedes `.10x/decisions/superseded/local-only-birding-product-architecture.md`. It preserves that decision's local Rufous, browser/API, model allowlist, and credential boundaries while replacing the single-local-warehouse constraint.

The compatibility basis is `.10x/tickets/cancelled/2026-08-31-prove-gbif-r2-iceberg-vertical-slice.md`.

## Decision

1. Rufous remains local. React MUST call the local FastAPI API and MUST NOT receive DuckDB, Polaris, R2, provider, or model credentials.
2. Apache Polaris will be the authoritative catalog for Iceberg tables in the lake.
3. A dedicated Cloudflare R2 bucket will hold Iceberg data and metadata. Its credentials MUST be restricted to that bucket.
4. Polaris will persist catalog state in PostgreSQL. Both PostgreSQL state and R2 objects are durable; ordinary Compose shutdown MUST NOT delete them.
5. Polaris and PostgreSQL will run in Docker Compose. Rufous data features backed by the lake are available only while the required Compose services and network access are available.
6. dlt will write lake tables through PyIceberg and the Polaris REST catalog. It MUST NOT maintain a second authoritative catalog for those tables.
7. Because R2 does not provide AWS `AssumeRole`, Polaris credential vending MUST be disabled for the R2 catalog. PyIceberg and DuckDB authenticate directly to R2 using one shared, bucket-scoped server-side lake credential pair. The credentials MUST never cross the FastAPI/browser boundary.
8. DuckDB remains the local query engine. SQLMesh remains the transformation framework for the first migration slice and materializes Rufous-owned transformed models into local DuckDB.
9. The first migration is a GBIF vertical slice. The existing GBIF-to-DuckDB path remains intact until parity and rollback evidence support an explicit cutover.
10. Existing GBIF behavior remains. Future direct eBird API use is additive and requires separate product/licensing shaping.
11. Public Rufous, Dagster containerization, SQLMesh state migration, other source migrations, and transformed-Iceberg materialization are outside the first slice.
12. The Cloudflare Workers AI model remains `@cf/zai-org/glm-4.7-flash`, with the existing no-fallback and server-side credential rules.

## Open-source principle and R2 exception

Apache Polaris, PostgreSQL, PyIceberg, DuckDB, SQLMesh, and the Iceberg format remain open source. Cloudflare R2 is a proprietary managed object store and is an explicit user-selected exception to the project's open-source-first rule because the user already operates a Cloudflare account and selected R2 as the durable storage target. The integration MUST remain limited to the standard S3-compatible API and Iceberg object layout; no R2-managed catalog or proprietary table format may become authoritative. This keeps the migration path to self-hosted MinIO, Ceph, or another S3-compatible store bounded to credentials, endpoint, and object transfer rather than application or table-format replacement.

## Alternatives considered

### Self-hosted MinIO or another open-source S3-compatible store

Not selected for this slice because the user explicitly chose the existing Cloudflare R2 account and accepted its managed runtime. It remains the preferred exit path if R2 compatibility, cost, privacy, or vendor dependence becomes unacceptable.

### Keep the single local DuckDB warehouse

Rejected as the long-term source-data architecture because it does not provide the requested durable, engine-independent Iceberg lake or REST catalog.

### Let dlt own an independent catalog

Rejected because multiple catalog authorities can produce undiscoverable tables or conflicting metadata histories. Polaris must own lake-table identity and commits.

### Materialize every SQLMesh model as Iceberg immediately

Rejected for the first slice. The installed SQLMesh DuckDB attachment configuration cannot express all Polaris options, direct materialization is unproven, and Rufous-owned derived models do not yet require cross-engine access.

### Replace SQLMesh with dbt before the slice

Rejected. Legacy `dbt-duckdb` does not remove the integration risk, newer catalogs-v2 support needs separate maturity and open-source verification, and a transformation-framework migration would obscure the lake compatibility proof.

### Containerize the whole Databox runtime immediately

Rejected for the first slice. Polaris/PostgreSQL, lake ingestion, transformation input, and orchestration relocation are independent changes. Combining them would make failures difficult to attribute.

## Consequences

- The platform is no longer storage-local even though Rufous remains runtime-local.
- Polaris availability and internet access to R2 become dependencies of lake-backed local Rufous features.
- PostgreSQL and R2 lifecycle procedures must prevent accidental catalog/data divergence.
- Existing Quack and local-DuckDB contracts remain authoritative for non-migrated sources during transition.
- GBIF migration must use parallel validation and preserve rollback.
- A later decision is required before transformed models move to Iceberg or SQLMesh is replaced.
