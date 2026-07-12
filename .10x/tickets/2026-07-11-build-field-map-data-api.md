Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
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

## Blockers

Census usage terms and exact source revision must be revalidated before committing the derived artifact.
