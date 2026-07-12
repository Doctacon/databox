Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: None

# Build Arizona bird wheel catalog

## Scope

Replace the paginated three-column card grid with a subtle vertical single-select name wheel and one identity-matched active preview while retaining all search/filter/sort/media/profile contracts.

## Acceptance criteria

- All interaction, semantic, visual, media, performance, responsive, and reduced-motion behavior in `.10x/specs/arizona-bird-wheel-catalog.md` passes.
- Wheel/trackpad/touch and Arrow/Page/Home/End interactions deterministically center one taxon.
- Search/filter/sort/reset semantics remain exact and reset to the first match.
- Only active preview creates photo/audio elements; no autoplay; changing taxon stops audio.
- Profiles/routes remain unchanged and no new dependency is added unless separately ratified.

## Evidence expectations

Focused DOM/keyboard/scroll-adapter/touch/reduced-motion/long-label/320px tests, 706-row render performance bound, full frontend suite, TypeScript/build/bundle audit, and accessibility review.

## Exclusions

No strong 3D cylinder, horizontal carousel, pagination, infinite network fetch, autoplay, profile redesign, or data-model change.

## Blockers

None.

## Progress and notes

- 2026-07-11: User selected a subtle curve rather than strong cylinder or flat list.
