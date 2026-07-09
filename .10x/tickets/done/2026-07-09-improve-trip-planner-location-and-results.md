Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: None
Depends-On: None

# Improve Trip Planner location and results

## Aggregate outcome

Improve the local Birding Trip Copilot so users can safely select Arizona places, receive geographically coherent plans, see common species names and useful weather, and play attributed Xeno-canto recordings inside the app.

This is a parent plan and is not executable directly.

## Governing specifications

- `.10x/specs/arizona-trip-location-resolution.md`
- `.10x/specs/trip-plan-result-presentation.md`
- `.10x/specs/xeno-canto-inline-audio.md`
- `.10x/specs/local-birding-trip-copilot-app.md`
- `.10x/specs/birding-trip-copilot.md`

## Child sequence

1. `.10x/tickets/done/2026-07-09-add-arizona-location-search-and-validation.md`
2. `.10x/tickets/done/2026-07-09-improve-species-and-weather-presentation.md`
3. `.10x/tickets/done/2026-07-09-add-inline-xeno-canto-audio.md`
4. `.10x/tickets/done/2026-07-09-verify-trip-planner-experience-improvements.md`

The sequence avoids concurrent writers in the React/API/planner surfaces. The species/weather and audio tickets are behaviorally independent but should execute sequentially because both modify the result UI.

## Aggregate acceptance criteria

- `Prescott, Arizona` is selectable through an accessible typeahead and resolves to Prescott, Arizona.
- `34.54,112.50` is rejected before evidence lookup with a negative-longitude explanation; `34.54,-112.50` resolves inside Arizona.
- No outside-Arizona location can receive Arizona-only bird recommendations.
- Uncommon recommendations show conformed common names when available, with smaller scientific names below.
- Weather shows actual persisted values in both unit systems rather than only source status.
- Xeno-canto audio streams through native controls with no local audio storage, while attribution/license/source links remain visible.
- API, SQLMesh, frontend, accessibility, security, source-provenance, CI, and docs checks pass.
- Independent review finds no unowned defect.

## Progress and notes

- 2026-07-09: User reported named-place failure, a missing-longitude-sign elevation mismatch, scientific-only uncommon species, unhelpful weather status, and link-only media.
- 2026-07-09: Inspection proved `34.54,112.50` is 112.5 degrees east and Open-Meteo reports 280 m there; `34.54,-112.50` reports about 1,686 m. The current planner also allowed arbitrary coordinates to bypass Arizona filtering while still querying Arizona datasets.
- 2026-07-09: User ratified Arizona-only location support, dual US/metric weather units, and accessible native inline audio.
- 2026-07-09: Open-Meteo geocoding returned Prescott, Arizona at approximately `34.54002,-112.4685`, elevation 1,638 m, timezone `America/Phoenix`. Xeno-canto direct download evidence returned `audio/mpeg` with permissive CORS.
- 2026-07-09: User explicitly authorized execution with the original request-time Open-Meteo plan; DuckDB remains the single system of record.
- 2026-07-09: Arizona location child completed after independent review and repair of geographic-boundary and timeout-contract findings.
- 2026-07-09: Species/weather child completed after authority-free conformance, production SQLMesh application, dual-unit presentation, and repair of source-name provenance through persisted API reload.
- 2026-07-09: Inline-audio child completed after canonical recording-identity, independent safe fallback, raw URL grammar, native accessibility, and no-storage review.
- 2026-07-09: Aggregate verification passed 11 SQLMesh tests, 66 focused Python tests, 27 React tests, full 213-test CI at 82.90%, strict docs, bundle/secret/audio audits, controlled Prescott create/reload, one successful no-fallback GLM 5.2 smoke, and production warehouse assertions. Evidence: `.10x/evidence/2026-07-09-trip-planner-experience-improvements-aggregate-verification.md`.
- 2026-07-09: Independent aggregate review returned pass with no unowned defect: `.10x/reviews/2026-07-09-trip-planner-experience-improvements-aggregate-review.md`.
- 2026-07-09: Retrospective: the work exposed three reusable boundary rules—geographic guards must model geography rather than rectangles, provenance must survive every bounded projection, and media safety requires cross-field identity plus independent safe fallback. Each rule is preserved by focused modules and adversarial regression tests in its child ticket; no additional knowledge or skill record is needed.

## Blockers

None.
