Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-evolve-product-into-rufous.md
Depends-On: .10x/tickets/done/2026-07-11-remove-wishlist-and-consolidate-watches.md, .10x/tickets/2026-07-11-add-catalog-card-and-profile-media.md, .10x/tickets/2026-07-11-add-trip-plan-calendar-controls.md

# Apply Rufous product identity and retro theme

## Scope

Implement `.10x/specs/rufous-product-shell.md` across settled routes using one original local CSS/SVG visual system and user-visible naming audit. Repository/package/database/internal identities stay unchanged.

## Acceptance criteria

- User-visible product brand/title is Rufous across shell/routes/docs; technical Databox names remain where required.
- Shared rust-orange/teal/cream/dark tokens, pixel-device panels, original Rufous motif, states, controls, cards, dialogs, media and responsive layouts are cohesive.
- No Pokémon asset/name/font/layout copy, remote font/theme request, proprietary dependency, or behavioral rewrite.
- Contrast, focus, keyboard, 320px/mobile/tablet/desktop, long text, zoom, reduced motion, native audio/image alt, live/busy and status semantics pass.
- Existing  product tests remain behaviorally green; theme DOM/CSS/screenshot-free contract tests and exact asset/network scans pass.

## Explicit exclusions

No repository/package/schema rename, copied game asset, canvas game, router/framework replacement, new product behavior, or adjacent backend change.

## Evidence expectations

Record naming audit, token/component coverage, route/state matrix, accessibility/responsive/reduced-motion checks, no-copyrighted/remote asset scan, bundle and full regressions.

## Blockers

Depends on structural UI children.
