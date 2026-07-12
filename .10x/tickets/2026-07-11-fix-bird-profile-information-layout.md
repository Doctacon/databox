Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
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

## Blockers

None.
