Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-improve-trip-planner-location-and-results.md
Depends-On: .10x/tickets/done/2026-07-09-add-arizona-location-search-and-validation.md

# Improve species and weather presentation

## Scope

Implement `.10x/specs/trip-plan-result-presentation.md` across SQLMesh planner interfaces, deterministic planner data, and React presentation.

Required work:

- make GBIF planner evidence use authority-free species names for conformance,
- recover eBird common names/species codes from the conformed species dimension without duplicate joins,
- preserve scientific names and source provenance,
- render common name as the card heading and scientific name below in smaller styling,
- render persisted Open-Meteo condition, temperature, humidity, precipitation, wind/gust, and elevation values,
- display deterministic US customary and metric conversions,
- translate persisted WMO weather codes into bounded human-readable conditions,
- keep source status and caveats visible but secondary,
- add SQLMesh regression tests and React tests for full and partial weather.

## Explicit exclusions

- No model-generated measurements or weather prose.
- No transient browser weather fetch.
- No unit preference/account system.
- No unrelated ranking-policy changes.
- No global taxonomy expansion.

## Acceptance criteria

- `Sialia mexicana Swainson, 1832`, `Melanerpes uropygialis (S.F.Baird, 1854)`, and `Aegolius acadicus (J.F.Gmelin, 1788)` can resolve to available eBird common names through authority-free conformance.
- Conformance does not multiply GBIF evidence or recommendations.
- Recommendation cards show common name first and smaller scientific name second when both exist.
- Weather displays condition, temperature range, humidity, precipitation, wind/gusts, and elevation in both unit systems from persisted data.
- Partial fields and source caveats remain clear.
- SQLMesh tests/prod plan, focused planner/API/frontend tests, CI, docs, and independent review pass.

## Evidence expectations

Record conformance query/test evidence, duplicate-count protection, rendered weather/species assertions, conversion tests, exact commands/results, and independent review.

## Progress and notes

- 2026-07-09: Added authority-free binomial normalization to the GBIF planner view and a guarded eBird-first conformed-species join. Raw/accepted scientific names and source provenance remain available; recommendation ranking is unchanged.
- 2026-07-09: Added SQLMesh regression coverage for Western Bluebird, Gila Woodpecker, Northern Saw-whet Owl, parenthesized/unparenthesized authorities, eBird precedence, and duplicate-dimension protection.
- 2026-07-09: Applied the selected view-only SQLMesh production plan to the single local DuckDB. A read-only production query returned all three conformed common names/codes, preserved 1,000 raw-to-view rows, and found zero duplicate evidence identifiers. Final `sqlmesh diff prod` reported no changes.
- 2026-07-09: Added deterministic dual-unit weather presentation from persisted Open-Meteo evidence, bounded WMO condition labels, individually labeled partial fields, visible caveats, and secondary source status.
- 2026-07-09: Added Python/API and React tests for conformed recommendations, stable forecast payload reload, full/partial weather, conversions, WMO labels, scientific-name styling, and scientific-only fallback.
- 2026-07-09: Validation passed: 11 SQLMesh tests; 29 focused Python tests; strict TypeScript, 14 React tests, and 30-module build; bundle audit; full CI with 210 tests at 82.48% coverage; strict docs build; final sequential pre-commit; and post-format focused React/SQLMesh reruns.
- 2026-07-09: Evidence recorded in `.10x/evidence/2026-07-09-species-and-weather-presentation.md`.
- 2026-07-09: Independent review found that `source_scientific_name` stopped at the SQLMesh view because the bounded planner projection omitted it, so persisted/API evidence could not distinguish the original GBIF name from accepted/conformed naming.
- 2026-07-09: Added `source_scientific_name` to the lookup and both source/accepted scientific names to the persisted summary; the payload retains the complete bounded row while recommendations continue using conformed `scientific_name`.
- 2026-07-09: Added an end-to-end POST/persist/GET regression with `Sialia occidentalis Townsend, 1837` as the source, `Sialia mexicana Swainson, 1832` as accepted, and `Sialia mexicana` as conformed. Strengthened the SQLMesh raw fixture to prove the source-to-view distinction. Repair checks passed 11 SQLMesh tests, 25 planner/API tests, two deterministic DeepEval tests, Ruff, format, and MyPy.
- 2026-07-09: Evidence updated with the review finding, exact repair behavior, regression path, commands, and limits.
- 2026-07-09: Independent re-review passed the SQL-to-planner-to-persistence-to-API provenance chain, duplicate protections, and deterministic full/partial weather behavior. Review: `.10x/reviews/2026-07-09-species-and-weather-presentation-review.md`.
- 2026-07-09: Retrospective: preserving provenance in a warehouse view is insufficient unless every bounded projection and persistence boundary carries it. The end-to-end source/accepted/conformed-name regression preserves that lesson; no separate knowledge or skill record is needed.

## Blockers

None.
