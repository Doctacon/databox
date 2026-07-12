Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-place-search-feedback-and-map.md
Depends-On: .10x/tickets/done/2026-07-11-add-local-hotspot-place-suggestions.md

# Persist structured observation locations

## Scope

Implement idempotent private schema migration, storage/service/API contracts, legacy preservation, and strict all-or-none validation from `.10x/specs/structured-observation-locations.md`.

## Acceptance criteria

- Existing personal observation(s) and free text remain byte/logically preserved with null structured fields.
- Selected source/id/name/coordinates/timezone/region persist atomically; free text persists without structure.
- Partial/mismatched/source-invalid/out-of-bounds inputs rollback; edit clears/replaces structure correctly.
- Private structured fields appear only in private collection APIs and never catalog/map/evidence/model/log surfaces.
- Migration inspect/apply/idempotency/rollback and full collection/privacy gates pass.

## Exclusions

No browser combobox, reverse/background geocoding, personal map, source data change, or observation lifecycle change.

## Evidence expectations

Record live preflight/count/checksum, migration invariants, structured/free-text attacks, surface absence, review.

## Blockers

Depends on strict suggestion identity contract.
