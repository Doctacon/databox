Status: cancelled
Created: 2026-08-31
Updated: 2026-09-03
Parent: None
Depends-On: None

# Prove the GBIF Iceberg vertical slice

## Outcome

Prove and, only after compatibility evidence, integrate a reversible GBIF path from dlt/PyIceberg through Apache Polaris into a dedicated Cloudflare R2 Iceberg warehouse, then through DuckDB and SQLMesh into the existing local FastAPI/Rufous behavior.

This is a parent plan, not an executable implementation ticket.

## Governing records

- `.10x/decisions/superseded/local-rufous-polaris-r2-iceberg-architecture.md`
- `.10x/specs/superseded/local-iceberg-databox-r2-platform.md`
- `.10x/specs/superseded/gbif-r2-iceberg-vertical-slice.md`
- `.10x/research/2026-08-31-polaris-r2-iceberg-compatibility.md`
- `.10x/specs/superseded/parallel-quack-local-refresh.md`
- `.10x/specs/canonical-dlt-source-registry.md`

## Plan and sequence

1. Execute `.10x/tickets/2026-08-31-prove-polaris-r2-client-compatibility.md`.
2. If the compatibility spike passes, use its exact versions and configuration evidence to open bounded implementation tickets for:
   - pinned Compose infrastructure and durable Polaris/PostgreSQL bootstrap;
   - parallel GBIF dlt/PyIceberg destination wiring;
   - DuckDB/SQLMesh Iceberg-source integration;
   - FastAPI unavailability handling and GBIF parity verification;
   - aggregate review, rollback proof, and closure.
3. If the spike fails, keep this parent open or blocked and shape only the smallest evidence-backed alternative. Do not silently substitute a different catalog, transformation framework, or managed service.

The post-spike tickets are intentionally not executable yet: exact released versions, R2 non-STS behavior, and client configuration are proof outputs rather than assumptions.

## Aggregate acceptance criteria

- The compatibility gate in `.10x/specs/superseded/gbif-r2-iceberg-vertical-slice.md` passes with reproducible evidence.
- Polaris and PostgreSQL use pinned versions and durable state.
- The GBIF lake table uses the dedicated R2 bucket and Polaris as its only catalog.
- The existing GBIF DuckDB path remains intact until parity and rollback are demonstrated.
- DuckDB reads GBIF through Polaris; SQLMesh materializes the existing Rufous model locally.
- Existing FastAPI/Rufous GBIF behavior passes defined parity checks.
- Polaris unavailability produces the ratified bounded error behavior.
- Public Rufous and all explicit exclusions remain unchanged.
- Each child ticket has criterion-mapped evidence and review before parent closure.

## Integration points

- `packages/databox-sources/databox_sources/gbif/source.py`
- `packages/databox/databox/config/settings.py`
- `packages/databox/databox/config/sources.py`
- `packages/databox/databox/orchestration/`
- `transforms/main/config.py`
- `transforms/main/models/birding_agent/catalog/gbif_occurrence_evidence.sql`
- `packages/databox/databox/api.py`
- `.env.example`
- Compose and operator documentation to be established after the spike

## Explicit exclusions

- Migration of non-GBIF sources
- Direct eBird API product changes
- Transformed Iceberg materialization
- dbt migration
- Dagster containerization or state migration
- Public Rufous changes
- Destructive catalog, volume, or R2 cleanup

## Evidence expectations

- Raw compatibility command output with secrets redacted
- Exact image, package, DuckDB core, and Iceberg extension versions
- Catalog/table/snapshot observations before and after restart
- Common-input GBIF parity output
- Focused and aggregate test output
- Secret scan
- Rollback proof
- Adversarial architecture/correctness/security review

## Progress and notes

- 2026-08-31: User ratified Polaris, PostgreSQL persistence, a dedicated durable R2 bucket, local FastAPI retention, a GBIF-first parallel slice, and deferred Dagster/SQLMesh state containerization.
- 2026-08-31: Research found dlt/PyIceberg and DuckDB support Polaris REST catalogs; generic non-STS S3 compatibility requires live proof with R2. Direct SQLMesh Iceberg materialization was removed from the first slice.
- 2026-08-31: Governing decision and focused specifications were activated. Only the compatibility spike is executable until version/configuration evidence exists.
- 2026-08-31: Execution started under `/loom-driver`; the compatibility spike is the only runnable child.
- 2026-09-01: User simplified R2 authentication to one shared bucket-scoped lake credential pair for PyIceberg and DuckDB; the compatibility child was reactivated to align the harness and attempt the bounded live proof.
- 2026-08-31: The compatibility harness and all credential-independent validation completed. Reviewer-requested repairs now separate the sole mutating fresh proof from exact read-only restart verification; fail closed on mismatched catalog, namespace, table placement, schema, metadata, snapshot, or row digest; validate a newly created table before append; suppress third-party exception text; and require exact key/value semantics plus an observed DuckDB snapshot transition across fresh clients.
- 2026-09-01: Shared lake credentials and Docker became available. Presence-only preflight and Compose health passed, but the sole permitted `fresh-proof` attempt failed closed with sanitized `stage=fresh-proof error=VerificationError`. It was not retried, `restart-verify` was not run, normal shutdown preserved the PostgreSQL volume, and no downstream implementation ticket is runnable.
- 2026-09-01: `.10x/tickets/2026-09-01-diagnose-failed-polaris-r2-proof.md` owns the separately scoped read-only diagnostic/recovery investigation.
- 2026-09-01: Independent review approved one exact read-only diagnostic invocation. It failed at presence-only preflight because the now-rejected redundant confirmation input was missing and stopped before any volume, Compose, Polaris, or R2 access. No preserved-state finding or new-identity proof recommendation is supported.
- 2026-09-01: User ratified `DATABOX_ICEBERG_VALIDATION_ID=validation-ticket-20260831` as the sole validation identity. The diagnostic repair retains exact fail-closed scope with that one value.
- 2026-09-01: After independent approval, the exact diagnostic runner was invoked once. Preflight and preserved-volume checks passed, but no-dependency Compose creation failed with sanitized `diagnostic-compose-create/CreateFailed`. Trapped stop/down completed without `-v` and post-down volume verification passed. No services or Polaris/R2 diagnostic started, so no preserved catalog/R2 structural conclusion or new-identity proof recommendation is supported.
- 2026-09-01: The Compose option mismatch was repaired and independently approved for one guarded invocation. Preparation, exact postgres/polaris-only service scope, distinct IDs, and stopped-state guards passed, but the PostgreSQL mount failed the reviewed exact tuple guard with sanitized `diagnostic-postgres-mount/UnexpectedMount` before start. Trapped cleanup completed without `-v` and preserved the volume. No Polaris/R2 finding or conditional new-identity proof is supported.
- 2026-09-01: The mount guard was repaired and independently approved. The next exact diagnostic runner invocation was executed once and reached read-only catalog validation. It failed with sanitized `diagnostic-catalog-storage/VerificationError`, exit `1`; cleanup completed without `ShutdownFailed` or `VolumeMissing`. This supports exact catalog presence, identity, and base location, but not exact storage validity, R2 prefix presence/count, namespace, table, metadata, or snapshot state. No retry or subsequent infrastructure mutation occurred.
- 2026-09-01: `.10x/tickets/2026-09-01-localize-polaris-catalog-storage-mismatch.md` now owns an offline-implemented, field-name-only localizer and a source-backed three-variant ladder. Polaris 1.7 normalization is classified separately from immutable bucket/prefix, endpoint-host, no-role/STS, and catalog-authority boundaries.
- 2026-09-01: After independent approval, the exact preserved-identity localizer was invoked once and exited `0`. Its only mismatch records were `allowedKmsKeys/server-default/harmless` and `allowedLocations/server-default/harmless`; cleanup completed without `ShutdownFailed` or `VolumeMissing`. No retry or mutation occurred.
- 2026-09-01: Before any Variant A work, the existing full diagnostic's storage verifier was narrowed to accept only those exact safe server-default shapes and reject every other unknown field, while preserving exact authority/storage guards. Offline focused/full gates passed.
- 2026-09-01: After independent approval, one full preserved-identity diagnostic exited `0`. The exact catalog and storage are valid; the bounded R2 prefix has zero objects; namespace, table, definition, and snapshot are absent. Cleanup and volume verification passed without fixed errors. No retry or mutation occurred.
- 2026-09-01: The sole independently approved Variant A runner invocation emitted `stage=variant-a-proof error=ProofFailed` and exited `1`. Cleanup and volume verification passed. The suppressed proof channels leave the internal stage and partial Variant A state unknown; no retry or inspection followed.

- 2026-09-02: Cancelled after the R2 compatibility path was retired and the user ratified AWS S3 as the durable Polaris/Iceberg object store. The later AWS migration supersedes this blocked proof; its failure history remains evidence rather than active work.

## Blockers

- Post-spike implementation decomposition is blocked on `.10x/tickets/2026-08-31-prove-polaris-r2-client-compatibility.md`.
- Live cross-client compatibility remains unproven.
- Stop the ladder. A separately reviewed read-only Variant A outcome localizer is required before any next decision. Restart verification, retry, Variant B/C, deletion, and ad hoc inspection are unauthorized.
