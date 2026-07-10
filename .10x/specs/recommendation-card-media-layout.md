Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Recommendation Card Media Layout

## Purpose and scope

This specification governs the Trip Planner result order and the presentation of persisted photo/call enrichment inside each recommendation card.

## Result order

After the persisted-plan hero and any plan-level caveat notice, the result MUST appear in this order:

1. Field Plan
2. Weather and Elevation
3. High-likelihood Species
4. Uncommon but Plausible Targets
5. Evidence and Provenance

- The standalone Call and Media Examples section MUST be removed.
- Evidence and Provenance MUST be the final result section.
- Persisted Agent Workflow traces MUST remain available inside the final Evidence and Provenance section using an accessible native disclosure such as `<details><summary>`.
- Evidence rows MUST remain visible independently of whether the workflow disclosure is expanded.

## Recommendation cards

Every high-likelihood and uncommon-plausible recommendation card MUST use the same media structure:

1. representative photo area,
2. rank, common name, and smaller scientific name,
3. confidence, rationale, and recommendation caveats,
4. one representative call area,
5. media attribution and safe source/license links.

### Photo

- An available photo MUST render with a bounded responsive aspect ratio and `loading="lazy"`.
- Alt text MUST identify the bird using the common name and scientific name when available; it MUST not invent behavior, sex, age, location, or visual details absent from metadata.
- Creator/rights-holder, recognized license, publisher/source, and a safe source link MUST appear in or directly below the photo area.
- If the image later fails to load, attribution and source/license information MUST remain visible.
- An unavailable photo MUST show a consistent visible placeholder stating that no licensed photo is available. The card and recommendation MUST remain intact.

### Call

- An available call MUST use the native audio player governed by `.10x/specs/xeno-canto-inline-audio.md`, with `controls`, `preload="none"`, and no autoplay.
- The card MUST display recording type, quality when available, recordist, license, source link, and scope label (`Arizona recording` or `Global example`).
- The player/source/license URL safety and canonical recording-ID constraints remain mandatory.
- If playback later fails, attribution and source/license information MUST remain visible.
- An unavailable call MUST show a consistent visible placeholder stating that no licensed call example is available.

## Card/media matching

- Photo and call objects MUST be attached by persisted `recommendation_id`, not by browser text matching.
- The UI MUST render no more than one selected photo and one selected call per card.
- Missing or malformed typed media MUST fail closed independently: a valid photo may remain when call data is invalid, and a valid call may remain when photo data is invalid.
- Media availability MUST NOT change card order, group, names, rationale, confidence, or caveats.

## Accessibility and responsive behavior

- Recommendation groups remain semantic sections with ordered card lists.
- Native image and audio semantics MUST remain keyboard/screen-reader accessible.
- Links MUST have descriptive text, safe `rel` behavior, and visible attribution context.
- Placeholders and failures MUST be visible text rather than color alone.
- Cards MUST remain readable at the current mobile breakpoints without horizontal scrolling.
- The final Agent Workflow disclosure MUST be keyboard operable through native semantics.

## Acceptance scenarios

### Available photo and Arizona call

Given a recommendation with available persisted photo and Arizona call objects, when the plan renders, then its card shows one lazy photo, one native audio player, `Arizona recording`, complete attribution/license/source links, and no duplicate standalone media card.

### Global call

Given a recommendation whose selected call uses global fallback, when the card renders, then the player remains available and `Global example` is visible.

### Independent unavailable states

Given a valid photo and unavailable call, when the card renders, then the photo remains active and the call placeholder is visible. The inverse behaves equivalently.

### Final order

Given a complete plan, when reading top to bottom after the hero/caveats, then sections appear as Field Plan, Weather and Elevation, High-likelihood Species, Uncommon but Plausible Targets, and Evidence and Provenance. No standalone Call and Media Examples section exists, and Agent Workflow is available inside the final section.

### Existing plan after backfill

Given the persisted Queen Valley plan after backfill, when reloaded without any GET-side network request, then each of its eight cards renders persisted photo/call results according to this contract.

## Explicit exclusions

- No media carousel, gallery, multiple-call list, waveform, autoplay, or lightbox.
- No separate Call and Media Examples section.
- No browser-side discovery or media persistence.
- No removal of evidence provenance or tool traces.
- No media-derived factual caption beyond source metadata.
