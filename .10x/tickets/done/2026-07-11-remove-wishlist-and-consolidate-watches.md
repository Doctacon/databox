Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-evolve-product-into-rufous.md
Depends-On: .10x/tickets/done/2026-07-10-build-my-birds-and-profile-controls.md

# Remove Wishlist and consolidate on Watches

## Scope

Remove wishlist runtime table/state, API endpoints, combined collection field, browser client/types/tests, profile control, and My Birds section under `.10x/specs/personal-bird-collection.md`. Add an explicit idempotent migration that records aggregate preconditions/counts, deletes any stale wishlist rows/table, and never creates watches.

## Acceptance criteria

- Wishlist routes return not found and no browser/runtime symbol or user-facing copy remains outside historical records/migration tests.
- Observation/life-list/watch behavior and collection-state relationships remain correct and independent.
- Live preflight confirms current zero rows; apply removes table safely, rerun is a no-op, rollback tests pass, and no watch/observation changes.
- My Birds and profile controls remain accessible/responsive with Watches as the sole prospective state.
- Full collection/API/frontend/privacy/docs/hooks pass.

## Explicit exclusions

No wishlist-to-watch conversion, watch semantic change, media, calendar invite, theme pass, or unrelated cleanup.

## Evidence expectations

Record zero-row live preflight, migration/apply/idempotency/rollback, API/UI absence scans, state counts before/after, and independent review.

## Progress and notes

- 2026-07-11: Removed wishlist table initialization, storage/service functions, typed API routes and collection-state field, browser client/types/UI/profile controls, active documentation, and stale test fixtures. Unknown wishlist GET/PUT/DELETE routes now return 404; observations and watches remain independent.
- 2026-07-11: Added explicit aggregate-only inspect/apply migration with transactional table drop, observation/watch count invariants, idempotent no-op behavior, and injected rollback tests. No wishlist row converts into a watch.
- 2026-07-11: Repaired two stale My Birds assumptions without weakening coverage: the error test now reaches the intended POST branch before its GET fixture, and cross-route mutation serialization asserts the active `Saving…` state, blocks the second mutation, supplies the required date, then proves the released form is enabled.
- 2026-07-11: Live preflight found the retired table with zero rows and zero neighboring observation/watch rows. Apply removed the table; read-only inspection and a second apply both reported table absent, zero removed rows, and unchanged zero neighboring counts. Live `birding_personal` now contains observations, watches, and watch-cancellation requests only.
- 2026-07-11: Validation passed 47 focused backend/API tests, all 417 network-disabled Python tests at 86.43% coverage, all 199 frontend tests plus TypeScript/build/bundle audit, MyPy (91 files), secret scan, all hooks, source layout 7/7, generated-doc freshness, and diff checks. Evidence: `.10x/evidence/2026-07-11-wishlist-removal-and-watch-consolidation.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-wishlist-removal-and-watch-consolidation-review.md`.
- 2026-07-11: Retrospective preserved explicit destructive-state migration and no-implicit-watch-conversion rules in the active specification and migration tests; no additional record is needed.

## Blockers

None.
