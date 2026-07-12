Status: done
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

None. The strict suggestion identity contract is complete.

## Progress and notes

- 2026-07-11: Implemented the idempotent six-column private migration, fresh-table constraints, service validation, strict private API request/response contracts, free-text fallback, atomic clear/replace behavior, and strict browser API validation. The ticket exclusion on adding an observation combobox was preserved.
- 2026-07-11: Focused backend passed 21/21, including fresh storage constraints, service rejection, API attacks, migration rollback/idempotency, and privacy checks. Full network-blocked Python passed 709/709 with three snapshots and 86.74% coverage; frontend passed 251/251 plus typecheck/build/bundle audit; MyPy, generated docs, repository secret scan, all-files pre-commit, and diff checks passed.
- 2026-07-11: After test completion, rehearsed rollback and apply-twice behavior on an isolated warehouse copy, then applied the migration twice transactionally to the live warehouse. The existing observation's original seven columns matched exactly, the safe checksum matched before/after, and all six structured fields are null. Evidence: `.10x/evidence/2026-07-11-structured-observation-locations.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-structured-observation-locations-review.md`.
- 2026-07-11: Retrospective preserved migration rehearsal and all-or-none privacy relationships in tests; no additional record is needed.
