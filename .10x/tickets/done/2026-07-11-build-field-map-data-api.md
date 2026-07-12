Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-repair-trip-planner-ebird-evidence-privacy.md

# Build Field Map data and API

## Scope

Implement the strict read-only observation snapshot API and bounded official Census-derived Arizona state/county GeoJSON artifact governed by `.10x/specs/rufous-field-map.md`.

## Acceptance criteria

- API returns only unique valid/reviewed/non-private, current-taxon, in-bounds Arizona evidence with bounded safe fields/freshness.
- Null/blank/missing/duplicate/private/invalid/unreviewed/out-of-bounds/malformed/unknown identity fails closed.
- `(private)` public name produces access warning without overriding privacy authority.
- GET is read-only/network-free and excludes personal/plan/watch/media/credential/trace/raw arbitrary fields.
- Census artifact provenance, source revision/terms, exact transformation, retained fields, counts, SHA-256 and size are recorded; no national excess.
- Strict backend/browser contracts and full Python/API/privacy/docs gates pass without warehouse mutation.

## Exclusions

No MapLibre UI/dependency, remote tile, personal data, routing, weather, range inference, or source refresh.

## Evidence expectations

Record live eligible counts/date range, adversarial eligibility matrix, no-write/no-network hash, artifact provenance/checksum, and independent review.

## Progress and notes

- 2026-07-11: Ratified and recorded the local internal contracts `GET /api/map-snapshot`, `app/src/assets/arizona-boundaries.geojson`, and maximum 10,000 encounters with a 10,001-row probe and safe 503/no truncation.
- 2026-07-11: Revalidated official Census TIGERweb January 1, 2025-vintage state/county layer metadata and current Census API usage terms. Fetched only `STATE='04'` geometry from layers 28/29, transformed one Arizona state plus 15 counties to deterministic local GeoJSON, and recorded source/terms/revision/commands/fields/count/hash/size in `.10x/evidence/2026-07-11-field-map-data-api.md`.
- 2026-07-11: Implemented strict backend and browser snapshot contracts over read-only persisted rows joined to current catalog identity. Exact flags, Arizona polygon, required bounded fields, duplicate/overflow/malformed relationships, and `(private)` access warnings fail closed; safe responses exclude raw/privacy/personal/plan/watch/media/credential/trace fields.
- 2026-07-11: Live network-forbidden read returned 1,575 unique encounters across 152 current taxa and 208 public locations, including three access warnings, from 2026-06-08 through 2026-07-09; warehouse SHA-256 remained unchanged.
- 2026-07-11: Focused backend/artifact/profile repair passes 23/23 and browser contract passes 17/17. Full network-blocked Python passes 701/701 at 86.63% coverage; frontend passes 245/245 plus typecheck/build/bundle audit; Ruff/format/MyPy/secrets/generated/docs strict gates pass.

- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-field-map-data-api-review.md`.
- 2026-07-11: Retrospective preserved endpoint/cap decisions, Census transformation provenance, and strict evidence eligibility in active records and tests; no additional record is needed.

## Blockers

None.
