Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`
Depends-On: `.10x/tickets/done/2026-07-11-migrate-catalog-and-map-curated-photos.md`

# Repair curated catalog refresh ownership

## Scope

Remove the persistence-ownership collision whereby the supported ordinary catalog refresh can reinterpret curated recommendation-photo evidence as GBIF-unavailable and overwrite valid curated catalog rows. Preserve GBIF only for occurrence context, never representative-photo activation.

## Acceptance criteria

- The supported `scripts/catalog_media.py --refresh`/ordinary catalog refresh path produces or preserves only valid `wikimedia_commons`, `inaturalist`, or typed curated-placeholder representative-photo rows.
- Starting from valid curated catalog rows, an ordinary refresh cannot replace them with a GBIF representative-photo row or legacy GBIF-typed unavailable row.
- Catalog refresh uses the shared curated selector boundary for representative photos while preserving separate GBIF occurrence-context behavior where applicable.
- Transition tests exercise valid curated starting state, ordinary refresh, failure/no-eligible cases, and persisted post-state validation.
- Completed valid curated identities remain resumable/idempotent; invalid or legacy rows are repaired through explicit controlled work rather than GET paths.
- GET paths remain network-free and write-free.
- Focused and full gates pass with no unrelated state mutation.

## Explicit exclusions

No new provider, catalog fact refresh, source refresh, recommendation behavior, UI redesign, or unrelated catalog-media refactor.

## Evidence expectations

Record a transition test that starts with valid curated rows and runs the supported refresh path, exact before/after provider/status counts, offline validation, GET purity checks, focused/full gates, and protected-state limits.

## References

- `.10x/specs/superseded/curated-representative-bird-photos.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-architecture-review.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-correctness-review.md`
- `.10x/evidence/2026-07-12-curated-representative-photo-aggregate-verification.md`

## Progress and notes

- 2026-07-12: Opened from aggregate architecture review blocker. No repair has begun.
- 2026-07-12: Ordinary catalog apply/refresh now owns representative photos through the shared curated selector only; GBIF representative-photo activation was removed while Xeno-canto calls remain separate. Two transition tests plus the curated selector suite passed (39 tests), as did targeted Ruff, format, MyPy, diff, and empty-staging checks. Evidence: `.10x/evidence/2026-07-12-curated-catalog-refresh-ownership-repair.md`. Self-review: `.10x/reviews/2026-07-12-curated-catalog-refresh-ownership-self-review.md`.

## Blockers

None. Full aggregate gates remain owned by the parent verification ticket.
