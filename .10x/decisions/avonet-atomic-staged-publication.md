Status: active
Created: 2026-07-10
Updated: 2026-07-10

# Use AVONET with atomic staged publication

## Context

This decision supersedes `.10x/decisions/superseded/avonet-only-modeled-bird-traits.md` while retaining its source, licensing, worksheet, conformance, coverage, provenance, and deterministic-presentation choices.

Implementation proved that `prepare_dlt_source` must force append disposition for Quack's beta attached-catalog path because Quack does not support the DELETE statements dlt emits for merge/replacement loads. Directly loading the supposedly complete AVONET snapshot into `raw_avonet` would therefore duplicate all 10,661 rows on a second run, retain rows removed by a changed snapshot, and risk exposing partial appended state after failure.

The source is static and version-pinned, but its active specification requires true authoritative replacement, production idempotency, and preservation of the last successful snapshot on extraction, load, validation, or publication failure.

## Decision

1. AVONET v7 remains the only new bird-trait source for the first Pokédex profile implementation, with the exact DOI/article/file/size/MD5/license and `AVONET2_eBird` boundaries established by the superseded decision.
2. AVONET remains an independently runnable dlt source with no daily schedule and no membership in shared parallel refresh.
3. dlt/Quack MUST write only to fixed internal schema `raw_avonet_staging`. Staging is never an authoritative product/source interface.
4. Before each run, stale staging from a crash or failed prior attempt MUST be removed while the Quack server is not running. The existing final `raw_avonet` schema MUST remain untouched.
5. After dlt completes successfully and the independent Quack server has stopped, one direct single-writer DuckDB transaction MAY publish the snapshot. This is a bounded post-Quack destination lifecycle operation analogous to existing physical raw-table maintenance, not concurrent direct ingestion.
6. Publication MUST first validate the exact expected physical column contract, 10,661 rows, 10,661 non-null unique Avibase IDs, 10,661 non-null unique source scientific names, and required source-scoped dlt metadata tables.
7. In one transaction, publication MUST replace `raw_avonet.species_traits` and required dlt metadata from staging, then remove staging. Any `BaseException` MUST roll back the final schema to its exact previous state.
8. Download, parse, staged-load, validation, or publication failure MUST leave the last successful final business and metadata tables unchanged. A failed first run MUST publish no final business table. Staging cleanup is best-effort on failure and mandatory before the next attempt.
9. Final successful state MUST contain no `raw_avonet_staging` schema and no persistent `main._dlt*` relation.
10. SQLMesh conformance remains exact normalized scientific name only. The measured 600/624 Arizona species matches, 24 taxonomy-drift species, and 82 unmatched hybrids remain explicit and unguessed.
11. Deterministic AVONET profile formatting and complete DOI/version/license/measurement/inference provenance remain mandatory. Missing traits and visual field marks MUST NOT be invented.

## Alternatives considered

- **Trust dlt `write_disposition=replace`:** rejected because production preparation rewrites it to append.
- **Append plus natural-key deduplication:** rejected because it cannot remove source rows absent from a later complete snapshot and does not protect authoritative state during a failed load.
- **Add AVONET to shared parallel refresh and publish during the server lifetime:** rejected because direct publication would create concurrent ownership and the static source does not need the daily lifecycle.
- **Backup/restore final tables around direct append:** rejected as more complex and riskier than never touching final state until validation succeeds.
- **Load directly with DuckDB instead of Quack:** rejected because source ingestion must retain the Quack ownership boundary.

## Consequences

- The source has a two-phase physical lifecycle: Quack staging, then atomic post-Quack publication.
- Orchestration and tests must distinguish internal staging from the stable `raw_avonet` interface.
- Crash recovery discards staging rather than attempting to resume it.
- The direct publisher must never run while the shared or independent Quack server is active.
- Documentation and evidence must describe physical atomic publication rather than claiming dlt itself performs replacement.
