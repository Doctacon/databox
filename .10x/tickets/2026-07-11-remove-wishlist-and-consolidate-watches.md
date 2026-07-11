Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-evolve-product-into-rufous.md
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

## Blockers

None.
