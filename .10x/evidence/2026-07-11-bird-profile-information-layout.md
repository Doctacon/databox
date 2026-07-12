Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-fix-bird-profile-information-layout.md, .10x/specs/bird-profile-information-layout.md

# Bird profile information layout evidence

## What was observed

- The profile main grid explicitly declares `grid-template-columns: minmax(0, 1fr)` with no viewport-dependent widening.
- The Photo and Call grid explicitly declares the same one-column track once in the base stylesheet. Its direct children have `min-width: 0`; the prior desktop `3fr / minmax(240px, 2fr)` split and redundant narrow override are absent.
- Profile photo attribution and call metadata scope `overflow-wrap: break-word` with `word-break: normal` on containers, children, and metadata links. This overrides the broader defensive wrap rule only for this requested profile surface.
- Rendered level-two panel order is exactly: Photo and call; Plan for this bird; Your collection; Identity and taxonomy; Ecology; Physical traits; Arizona activity; Occurrence and sound context; Evidence and provenance.
- The Photo DOM node precedes the Call DOM node. Long photographer and recording-locality strings with ordinary spaces render in the attribution and metadata containers.
- The existing 540px rule leaves 296px of content width at a 320px viewport through 12px horizontal profile padding; neither media track nor child introduces a positive minimum width.

## Procedure and results

- `cd app && npm test -- --run src/BirdPages.test.tsx && npm run typecheck` — 25/25 focused tests and typecheck passed.
- `cd app && npm run typecheck && npm test -- --run && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — 224/224 frontend tests passed; typecheck, production build, and bundle privacy audit passed.
- `git diff --check` — passed.

Existing regressions in the full suite cover detail loading/error/unavailable behavior, photo and call loading failures, source/license/selection/freshness metadata, playback and single-active-audio cleanup, collection controls and mutations, native navigation, focus/history/title behavior, exact facts and units, and sparse/unavailable profile content.

## Limits

JSDOM does not perform browser layout. The 320px guarantee is therefore established by the exact base one-column/min-width CSS contracts, narrow profile padding contract, absence of the former positive media track minimum, and rendered long-metadata DOM rather than a screenshot. Independent review remains required before closure.
