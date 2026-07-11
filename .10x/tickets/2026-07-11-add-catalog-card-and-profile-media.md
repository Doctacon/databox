Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-evolve-product-into-rufous.md
Depends-On: .10x/tickets/2026-07-11-implement-catalog-media-enrichment.md

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

## Blockers

Depends on catalog media API.
