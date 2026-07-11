Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-evolve-product-into-rufous.md
Depends-On: .10x/tickets/done/2026-07-11-implement-catalog-media-enrichment.md

# Add catalog card and profile media

## Scope

Render strict catalog media on Arizona Birds cards and profiles under `.10x/specs/arizona-catalog-media.md`: lazy photos/placeholders, compact one-active-at-a-time Play/Stop calls, full profile media/attribution, unavailable/load-error states, and strict browser validation.

## Acceptance criteria

- Every card/profile displays available exact media or deliberate Rufous unavailable placeholder/status without parent inference.
- Images are lazy, safe, responsive, attributed, and preserve attribution on load failure.
- Calls use accessible Play/Stop, `preload=none`, one active stream, stop on route/page/filter changes, and safe error state.
- Profile shows creator/recordist/source/license/scope/selection/freshness.
- Paging/search/filter/direct/history/focus/keyboard/mobile behavior and existing catalog/planner tests pass.
- Unsafe/malformed/mismatched API media never activates or partially renders.

## Explicit exclusions

No media discovery/write, autoplay, binary storage, custom waveform, theme-wide styling, or new provider.

## Evidence expectations

Record exact available/unavailable/hybrid/drift/load-error cases, audio exclusivity/lifecycle, attribution, browser trust-boundary attacks, responsive/accessibility and full frontend gates.

## Progress and notes

- 2026-07-11: Implemented strict catalog-card and profile media rendering with responsive lazy photos/original Rufous unavailable placeholders, compact one-active Play/Stop calls, complete profile attribution/scope/selection/freshness, and preserved attribution on bounded image/audio errors.
- 2026-07-11: Diagnosed the pagination lifecycle failure: React detached the audio DOM ref before passive child cleanup, so cleanup could not pause the element. Retained only the actively playing element until stop/end so page, filter, route, and unmount cleanup pauses and rewinds the actual stream without weakening the regression test.
- 2026-07-11: Focused BirdPages passed 22/22. Full `task app:check` passed strict TypeScript, 205 frontend tests, production build, and the 12-name/10-value bundle privacy audit. Repository secret scan, diff check, and no-stage gate passed. Evidence: `.10x/evidence/2026-07-11-catalog-card-and-profile-media.md`.
- 2026-07-11: Independent review passed every media, attribution, audio lifecycle, browser boundary, responsive, accessibility, history, and focus criterion. Review: `.10x/reviews/2026-07-11-catalog-card-and-profile-media-review.md`.
- 2026-07-11: Retrospective captured the React ref-detachment audio-cleanup failure and regression in the ticket/evidence; the focused test permanently protects the behavior, so no additional record is needed.

## Blockers

None.
