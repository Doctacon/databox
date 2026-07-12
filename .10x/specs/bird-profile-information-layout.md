Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Bird profile information layout

## Purpose

Make bird profiles readable at narrow and wide viewports without changing facts, media, collection actions, or routes.

## Layout

The profile main grid MUST explicitly use one content column at every viewport. Panels appear in this order:

1. Back link and identity hero
2. Photo and Call
3. Plan for this bird
4. Private collection controls
5. Identity and taxonomy
6. Ecology
7. Physical traits
8. Arizona activity
9. Occurrence and sound context
10. Evidence and provenance

Ecology MUST be full width and precede Physical traits.

Within Photo and Call, media MUST stack vertically at every viewport: Photo first, Call second. Photo attribution and Call metadata MUST use available width and wrap without narrow side columns, per-character wrapping, overflow, or clipping. Existing unavailable/load-error, source/license, playback, focus, and one-active-audio behavior remains unchanged.

## Acceptance scenarios

- At desktop width, Ecology is above Physical traits rather than beside it.
- At 320px, photo attribution and call metadata remain readable with normal word wrapping.
- Photo always precedes Call.
- Reordering does not change headings, values, collection actions, media URLs, or route/history behavior.
