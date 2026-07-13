Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/cancelled/2026-07-12-repair-curated-selector-source-integrity.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Curated selector live-provider preflight blocker

## What was observed

The combined repaired implementation passed all non-live Python and static gates after deterministic planner/API/catalog harnesses were updated to use the explicit curated-photo transport and no-op test-only iNaturalist limiter seam. The bounded live Wikimedia-first confirmation then failed closed before any project DuckDB mutation because the Wikidata Query Service did not return the exact-P225 metadata response.

The production selector returned typed unavailable for `Trogon elegans` with caveat `Wikimedia exact-taxon discovery was unavailable or malformed` and attempted sources `wikimedia_commons` only. A direct governed `_get_json` exact-P225 request returned the sanitized `RuntimeError('curated-photo metadata discovery failed')`. A separate bounded curl request to the same generated public WDQS query with the descriptive Rufous user agent timed out after 30 seconds with zero response bytes. Under the active spec, Wikimedia transport failure MUST stop rather than fall through to iNaturalist, so neither the full catalog nor saved-plan re-evaluation was launched.

## Procedure and results

### Deterministic harness repair

The planner runtime and local API now expose explicit injected curated-photo transport and test-only limiter hooks through the existing call chain. Production defaults remain `None`, preserving the real iNaturalist limiter. Planner, API, and CLI tests inject deterministic curated metadata plus a no-op limiter; the request-time cardinality test additionally forbids the module's live `_get_json` path. Catalog tests with deterministic custom curated transports inject the existing no-op limiter hook. The interrupted photo-refresh fixture now explicitly seeds invalid legacy provider labels in its temporary test DuckDB rather than weakening production completion validation.

- Focused planner/API/media/catalog/selector suite: 136 passed in 6.96 seconds.
- Full Python: 786 passed, three snapshots passed, 86.27% coverage in 169.34 seconds.
- Combined frontend repair pass was already recorded by `.10x/evidence/2026-07-12-curated-photo-frontend-contract-repair.md`: strict TypeScript, 300 tests, production build, and bundle audit passed.
- Ruff check/format, MyPy (99 source files), secret scan, generated staging/platform-health/docs checks, 13 SQLMesh tests, strict MkDocs build, seven-source layout check, all 11 pre-commit hooks, `git diff --check`, and empty staging passed.

### Read-only preflight

No Quack, SQLMesh, Uvicorn, source-refresh, catalog-media apply/refresh, recommendation-media apply, or competing DuckDB writer was present. `lsof data/databox.duckdb` returned no handle.

`/tmp/curated_final_state_snapshot.py` used read-only DuckDB access and conditionally tolerated the expected pre-upgrade absence of `provider_outcomes_json`; it did not mutate schema. `/tmp/curated-final-pre.json` recorded:

- catalog: 706/706 valid current rows; 621 available iNaturalist and 85 typed curated placeholders;
- planner: one plan, eight recommendations, eight available iNaturalist photos, zero invalid/missing/duplicate photos;
- 86 protected fingerprints, including exact call and non-photo planner evidence subsets;
- 19 protected external-file hashes.

Catalog photo dry-run reported 706 explicit refresh targets, zero lookups/writes. Saved-plan ordinary dry-run reported one plan/eight recommendations, zero missing/duplicates/targets, and zero lookups/writes.

### Bounded live confirmation

The exact confirmation required an available Wikimedia result, a provider thumbnail width no greater than 1024, and zero iNaturalist endpoints/callbacks. It failed before those assertions because WDQS exact-name discovery was unavailable. No iNaturalist request occurred.

After the failed metadata probes, `/tmp/curated-final-postprobe.json` exactly matched the preflight snapshot for all 86 protected fingerprints, all 19 external hashes, catalog/planner photo counts, photo-run fingerprint/values, and current validation counts. No DuckDB handle remained.

## What this supports

This supports that the deterministic repairs and combined code pass required non-live gates, tests make no live curated-provider calls, production rate limiting was not weakened, and the authorized live phase stopped at the required safe boundary. It also proves no project database or protected external state changed during this attempt.

## Limits and blocker

Current WDQS availability prevented proof that the production selector now chooses an eligible Wikimedia candidate. The current catalog/planner rows remain the pre-repair iNaturalist/placeholder state. The two exactly-once serialized re-evaluation commands were deliberately not run. The owning ticket must remain blocked until a later bounded WDQS confirmation succeeds; only then may the already-authorized catalog and saved-plan re-evaluations proceed with fresh writer preflight and fingerprints.
