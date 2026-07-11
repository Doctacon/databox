Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-evolve-product-into-rufous.md
Depends-On: .10x/tickets/done/2026-07-11-remove-wishlist-and-consolidate-watches.md, .10x/tickets/done/2026-07-11-add-catalog-card-and-profile-media.md, .10x/tickets/done/2026-07-11-add-trip-plan-calendar-controls.md

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

## Progress and notes

- 2026-07-11: The reviewed catalog-media backend and live metadata are complete. Theme sequencing remains unchanged: catalog/profile media presentation and trip-plan calendar controls must settle before theme work begins.
- 2026-07-11: Implemented the Rufous display identity, original local bird motif, shared rust/teal/cream/dark device tokens, route/component/state styling, narrow responsive shell, visible focus, non-color state markers, contrast and reduced-motion contracts. Updated current app/docs/API/alert display naming while preserving package, repository, database, and internal identities. Added static theme/naming/network/accessibility contracts and updated route title/responsive tests. Full Python (461), frontend (221), type, build, bundle, privacy, docs, lint, format, mypy, secret, drift, and hook checks pass. Evidence: `.10x/evidence/2026-07-11-rufous-product-theme.md`.
- 2026-07-11: Repaired the naming-review failure in `docs/commands.md`: Rufous is now the acting product for media proxying and alert cancellation wording. Strengthened the current user-facing shell/docs scan to reject any standalone Databox product-brand leak while preserving explicit technical package/database identity checks. Focused naming/lint/format, strict docs, and the full 461-test Python suite pass.
- 2026-07-11: Independent follow-up review passed naming boundaries, originality/no-remote-assets, route/state token coverage, responsive/accessibility/reduced-motion, technical-identity preservation, and evidence accuracy. Review: `.10x/reviews/2026-07-11-rufous-product-theme-review.md`.
- 2026-07-11: Retrospective preserved the product-vs-technical naming distinction in a broad static regression test; no separate record is needed.

## Blockers

None; all structural UI dependencies are done.
