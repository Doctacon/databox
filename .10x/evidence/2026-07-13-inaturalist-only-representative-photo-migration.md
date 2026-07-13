Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Relates-To: `.10x/tickets/done/2026-07-13-migrate-inaturalist-only-representative-photos.md`, `.10x/specs/curated-inaturalist-representative-bird-photos.md`

# iNaturalist-only representative-photo migration evidence

## What was observed

The exactly-once serialized catalog and saved-plan photo migrations completed under the active iNaturalist-only contract. All 706 catalog identities now have one strict current result: 622 available iNaturalist photos and 84 typed unavailable placeholders. All eight saved Trip Planner recommendations have one strict available iNaturalist photo. No Wikimedia or GBIF representative-photo rows remain.

The migration changed only owned representative-photo evidence and photo-run metadata. Eighty-six protected database table/subset fingerprints and 19 external file hashes were identical before migration, immediately after migration, and after all gates.

## Procedure and results

### Preflight and bounded live probe

- Process inspection and `lsof data/databox.duckdb` found no Quack, SQLMesh, Uvicorn, source-refresh, catalog-media, recommendation-media, Dagster, DuckDB, or other competing writer/handle.
- Read-only preflight found 706 catalog identities, one plan/eight recommendations, zero planner duplicates, 86 protected fingerprints, and 19 external files. Only 82 old typed placeholders met the new strict provenance contract; the remaining old rows were correctly migration targets.
- A bounded production-path `Trogon elegans` probe called only `https://api.inaturalist.org/v2/taxa` and exact-ID `https://api.inaturalist.org/v1/taxa/20781`. It invoked both governed rate callbacks, selected strict available photo `419827917`, passed offline validation, and made no binary request.

### Exactly-once catalog migration

The only catalog apply command was:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/catalog_media.py --database-path data/databox.duckdb --batch-size 706 --refresh-photos
```

Result:

```text
mode=photo_refresh run_id=catalog_photo_617cb94de24c470b89c8b7ff1e8ca447 catalog_count=706 target_taxa_count=706 processed_taxa_count=706 complete_taxa_count=706 remaining_taxa_count=0 lookup_count=624 available_photo_count=622 unavailable_photo_count=84
```

The terminal run record is `complete`, with 624 exact-binomial lookups and bounded outcomes:

```json
{"inaturalist.available": 622, "inaturalist.no_eligible": 2}
```

The other 82 unavailable results were non-queryable identities such as hybrids/non-binomial rows and required no provider lookup. Catalog call coverage remained 600 available/106 unavailable and was protected from photo migration.

### Exactly-once saved-plan migration

After the catalog writer exited, the only planner apply command was:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m databox.agent_tools.recommendation_media_backfill --database-path data/databox.duckdb --curated-photos
```

Result:

```text
mode=apply plan_count=1 recommendation_count=8 target_recommendation_count=8 replaced_photo_count=8 inserted_photo_count=8 inserted_available_count=8 inserted_unavailable_count=0 inserted_call_count=0 lookup_count=8 duplicate_media_count=0 remaining_missing_photo_count=0 remaining_missing_call_count=0
```

The two DuckDB writers never overlapped. Neither apply command was rerun; no rows were manually deleted or reset.

### Post-state, API, and no-op inspection

- Read-only reconstruction validated 706/706 strict catalog singletons: 622 `inaturalist:available` and 84 `curated_photo:unavailable`.
- Read-only reconstruction validated eight/eight strict saved-plan singletons: eight `inaturalist:available`, zero missing/invalid, and zero duplicates.
- SQL inspection found zero Wikimedia or GBIF representative-photo rows.
- Curated planner dry-run returned zero targets, zero lookups, zero duplicates, and zero missing photos/calls. Catalog completion inspection found the latest run complete at 706/706 and all 706 persisted results full-contract valid. No second apply was used to prove no-op completion.
- With provider discovery replaced by a forbidden function, TestClient GETs returned 200 for the supported JSON catalog `/api/birds`, compatibility/static route `/api/v1/birds`, and browser route `/birds`. The `/api/birds` JSON contained all 706 birds with 622 available photos and 84 typed placeholders. The DuckDB SHA-256 was unchanged across GETs.

### Protected-state comparison

The pre-, post-, and post-gate snapshots matched exactly for 86 protected database fingerprints and 19 external hashes. Protected coverage includes all non-photo tables plus catalog call rows and non-photo Trip Planner evidence. This supports unchanged:

- catalog/recommendation facts, IDs, order, confidence, rationale, timestamps, locations, and weather;
- all recommendation calls and GBIF occurrence context;
- personal observations and Watches;
- calendar and outbox;
- source-refresh state and credentials/configuration tables;
- warehouse/SQLMesh and unrelated runtime state;
- external data files.

Personal row values were not copied into this record.

### Post-migration gates

- Focused Python: 159 passed.
- Focused frontend: strict TypeScript plus 145 assertions across curated validator, BirdPages, Field Map, planner validation, and App.
- Full Python: 776 passed, three snapshots passed, 86.33% coverage.
- Full frontend: 295 passed; strict TypeScript, production build, and configured bundle audit passed. Vite emitted only the existing large MapLibre chunk advisory.
- Ruff check/format, MyPy for 99 source files, secret scan, staging/platform-health generation checks, 13 SQLMesh tests, docs generation, strict MkDocs build, source-layout checks, all 11 pre-commit hooks, `git diff --check`, and empty staging passed.

## What this supports

This supports every migration-ticket criterion: exactly-once serialized iNaturalist-only re-evaluation; complete strict catalog/planner cardinality; mixed-placeholder API/browser availability; network/write-free GET and completion inspection; zero model/email/source/AVONET/call refresh or binary work; and protected-state preservation.

## Limits

Provider-hosted image URLs can later become unavailable or change remote content because Rufous intentionally stores metadata rather than binaries. Automated tests and TestClient do not establish physical-browser layout, assistive-technology announcements, live remote-image loading, or visual subject quality. `/api/v1/birds` currently resolves successfully through the app compatibility/static routing; the governed JSON catalog endpoint is `/api/birds`.
