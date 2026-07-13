Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Relates-To: `.10x/tickets/done/2026-07-13-implement-inaturalist-only-representative-photos.md`, `.10x/specs/curated-inaturalist-representative-bird-photos.md`

# iNaturalist-only representative-photo implementation evidence

## What was observed

Rufous now has one active representative-photo source: the curated iNaturalist taxon-photo shortlist. Active Python and browser implementation no longer contains Wikimedia/Wikidata/WDQS/Commons source discovery, ranking, URL validation, provider unions, or operational endpoints. The only remaining `wikimedia_commons` strings are three adversarial frontend tests proving the legacy provider is rejected.

Typed unavailable catalog photos now accept either null scientific identity or the exact containing scientific identity while requiring every active-media field to remain null. A mixed catalog containing an exact-identity unavailable row and a strict iNaturalist available row validates successfully. Malformed unavailable metadata still fails closed.

## Procedure and results

### Focused deterministic gates

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest --no-cov -q tests/test_curated_photo.py tests/test_catalog_media.py tests/test_recommendation_media.py tests/test_recommendation_media_backfill.py tests/test_bird_catalog_api.py tests/test_map_snapshot_api.py tests/test_birding_trip_planner.py tests/test_api.py`: 172 passed.
- `cd app && npm run typecheck && npm test -- --run src/curatedPhotoValidation.test.ts src/BirdPages.test.tsx src/FieldMap.test.tsx src/tripPlanValidation.test.ts src/App.test.tsx`: strict TypeScript passed; focused frontend suites passed after the mixed unavailable fixture was made non-mutating. The final component totals represented 145 focused assertions (13 validator, 38 planner validation, 7 Field Map, 58 App, 29 BirdPages).
- Deterministic selector coverage proves v2 exact active species identity, v1 cross-version identity, curated shortlist order, first eligible selection, non-binomial no-network behavior, quality floor, licenses, attribution sanitization, exact URL/photo identity, redirect/final-origin failure, typed unavailable results, bounded outcome keys, daily request budget, and legacy attempted-source/provider rejection.

### Full gates

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest`: 776 passed, three snapshots passed, 86.33% coverage.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py`: 295 tests passed; TypeScript and production build passed; 12 configured names and 10 configured values were absent from the bundle. Vite emitted only the existing large MapLibre chunk advisory.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`: passed; 162 files formatted.
- `.venv/bin/mypy packages/`: passed for 99 source files.
- Secret scan, staging/platform-health generation checks, docs generation, strict MkDocs build, source-layout check, all 11 pre-commit hooks, `git diff --check`, empty staging, and 13 non-mutating SQLMesh tests passed.

### Active-source deletion and read-only app proof

- Bounded source grep over `packages/databox/databox`, non-test `app/src`, and `scripts` found no Wikimedia, Wikidata, Commons provider, WDQS, P225, P18, or `wikimedia_commons` representative-photo logic. Creative Commons license strings remain as required licensing metadata, not a media provider.
- The only legacy source strings found were in `app/src/curatedPhotoValidation.test.ts`, `app/src/tripPlanValidation.test.ts`, and `app/src/BirdPages.test.tsx`, each mutating an otherwise valid row to `wikimedia_commons` and asserting rejection.
- A read-only TestClient request against the current project DuckDB returned HTTP 200 and all 706 catalog rows. Because persisted rows still carry the superseded attempted-source provenance pending the separately owned migration, the new strict backend safely exposed 706 typed placeholders rather than failing the whole catalog. The DuckDB SHA-256 was identical before and after the GET.

## What this supports

This supports the implementation ticket acceptance criteria: iNaturalist v2/v1-only discovery; removal of active Wikimedia source logic; strict iNaturalist/typed-unavailable contracts across selector, persistence, API, and browser; mixed-placeholder catalog loading; provider/URL/license/identity attacks failing closed; GET purity; and complete deterministic/full gate success without live provider or project database mutation.

## Limits

This evidence does not claim that current persisted catalog/planner rows have been re-enriched under the new provenance contract. That live, serialized work belongs to `.10x/tickets/done/2026-07-13-migrate-inaturalist-only-representative-photos.md`. Current strict reads deliberately degrade superseded rows to placeholders until migration. No physical-browser, responsive-device, screen-reader, live remote-image, or visual subject-quality session was performed. Provider-hosted images can later become unavailable because binaries are intentionally not stored.
