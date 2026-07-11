Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: None
Depends-On: .10x/tickets/done/2026-07-09-build-local-birding-pokedex.md

# Evolve the product into Rufous

## Aggregate outcome

Turn the completed local birding Pokédex into Rufous: media-rich Arizona catalog cards/profiles, Watch-only prospective collection, explicit trip-plan calendar invitations, and an original rust-orange/teal GBA-era field-device visual system.

This is a parent plan and is not executable directly.

## Governing records

- `.10x/decisions/rufous-product-identity-and-retro-visual-direction.md`
- `.10x/decisions/catalog-media-and-watch-only-collection.md`
- `.10x/decisions/trip-plan-calendar-invitation-lifecycle.md`
- `.10x/specs/arizona-catalog-media.md`
- `.10x/specs/personal-bird-collection.md`
- `.10x/specs/trip-plan-calendar-invitations.md`
- `.10x/specs/rufous-product-shell.md`
- Existing media, catalog, planner, calendar/outbox, SMTP, privacy, and accessibility contracts remain active.

## Delivery sequence

1. Remove Wishlist through `.10x/tickets/done/2026-07-11-remove-wishlist-and-consolidate-watches.md`.
2. Implement catalog media storage/batch/API through `.10x/tickets/2026-07-11-implement-catalog-media-enrichment.md`.
3. Add catalog/profile media presentation through `.10x/tickets/2026-07-11-add-catalog-card-and-profile-media.md`.
4. Implement trip-plan calendar state/API/transport through `.10x/tickets/2026-07-11-implement-trip-plan-calendar-invitations.md`.
5. Add trip-plan invitation controls through `.10x/tickets/2026-07-11-add-trip-plan-calendar-controls.md`.
6. Apply Rufous product identity/theme through `.10x/tickets/2026-07-11-apply-rufous-product-theme.md` after product surfaces settle.
7. Run aggregate verification through `.10x/tickets/2026-07-11-verify-rufous-product-evolution.md`.

Catalog media backend and trip-calendar backend are parallelizable after shaping; their UI children depend on their respective APIs. Wishlist removal is independent. Theme follows all structural UI changes to avoid duplicate restyling.

## Aggregate acceptance direction

- Arizona Birds cards and profiles show exact validated photo/call media or deliberate unavailable placeholders with attribution.
- Wishlist is absent from storage/API/UI and Watch is the sole prospective-interest state.
- Completed trip plans can explicitly send/update one stable calendar event through the configured Bridge without implicit sends.
- Every route presents Rufous identity and the original accessible retro field-device visual system.
- No copyrighted Pokémon asset/layout, media binary storage, parent-species media inference, credential leak, duplicate calendar event, or regression to the completed Pokédex contracts.

## Blockers

None; execute bounded children in dependency order.
