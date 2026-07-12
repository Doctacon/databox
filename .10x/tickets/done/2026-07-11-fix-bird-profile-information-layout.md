Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-add-catalog-card-and-profile-media.md

# Fix bird-profile information layout

## Scope

Implement `.10x/specs/bird-profile-information-layout.md`: explicit one-column profile grid, stacked Photo then Call, and full-width Ecology before Physical traits.

## Acceptance criteria

- Panel DOM/visual order exactly matches the specification.
- Photo/call and attribution/metadata never form narrow side columns or per-character wrapping at desktop or 320px.
- Existing facts, media lifecycle, collection actions, headings, focus/history, unavailable/error and accessibility behavior remain unchanged.
- Full frontend/type/build/bundle gates pass.

## Exclusions

No content/data/API change, new panel, catalog controls, map, or broad theme redesign.

## Evidence expectations

Record DOM order, desktop/320px CSS contracts, long metadata, media/error and full regressions.

## Progress and notes

- 2026-07-11: Made the profile main grid and Photo/Call media grid explicitly one-column at all widths, removed the now-redundant narrow breakpoint override, and constrained media children to available width.
- 2026-07-11: Moved the unchanged Ecology panel before the unchanged Physical traits panel. All other panels, content, actions, media behavior, routes, and accessibility semantics remain in their prior order.
- 2026-07-11: Scoped normal word wrapping to profile photo attribution and call metadata, including children and links. Added exact DOM order, Photo-before-Call, long spaced metadata, one-column CSS, child width, and 320px padding contract coverage.
- 2026-07-11: Focused profile/catalog tests pass 25/25. Full frontend passes 224/224 plus typecheck, production build, and bundle privacy audit. Evidence: `.10x/evidence/2026-07-11-bird-profile-information-layout.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-bird-profile-information-layout-review.md`.
- 2026-07-11: Retrospective captured the inherited generic-main grid as an explicit CSS regression; no additional record is needed.

## Blockers

None.
