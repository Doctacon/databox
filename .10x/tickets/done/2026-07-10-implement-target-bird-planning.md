Status: done
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/done/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-09-build-arizona-bird-catalog-and-profile.md

# Implement target-bird planning

## Scope

Implement the target-specific persistence/service, typed API, strict GLM workflow, weather integration, and React “Find this bird” flow governed by `.10x/specs/target-bird-planning.md`.

Reuse exact Arizona resolution and planner timing boundaries; validate radius 1–300 miles; rank at most ten exact-species valid/reviewed/non-private public location clusters by the specified count/newness/distance/stable ties; persist request, evidence, weather, report, provenance, and sanitized traces atomically.

## Acceptance criteria

- Haversine filtering/ranking and coherent location metadata exactly exclude wrong species, private, invalid, unreviewed, and outside-radius rows.
- Requests require current catalog species, Arizona origin, 1–300 miles, local start, and 1–1440-minute duration; distances display miles and kilometers.
- Open-Meteo runs only after ranking and degrades honestly; empty evidence never broadens radius or invents locations.
- Sole `@cf/zai-org/glm-5.2` strict-schema report is exactly grounded; model failure rolls back without fallback/repair/timeout weakening.
- POST creation is serialized/atomic; GET list/detail are network-free/read-only and reproduce persisted artifacts.
- Profile action, form, results, direct/history/focus/accessibility/responsive/error states pass while existing Trip Planner remains behaviorally independent from personal state.
- Secrets/private locations/personal origins are absent from logs, traces, bundles, and committed fixtures.

## Explicit exclusions

No route/driving API, map, saved home, watch creation, personal-history personalization, alert delivery, external bird facts, alternate model, or access guarantee.

## Evidence expectations

Record deterministic ranking/distance fixtures, grounding/schema tests, atomic rollback, weather states, empty evidence, no-write GET replay, privacy/secret/bundle audits, UI/accessibility checks, and full planner/catalog regression.

## Progress and notes

- 2026-07-10: Ticket derives from explicit date/time/duration plus 1–300-mile per-request target-planning decisions.
- 2026-07-10: Implemented exact public eBird candidate clustering, distinct-submission counts, coherent newest metadata, true Haversine filtering, deterministic count/newness/distance/name/ID ranking, post-ranking weather, strict sole-GLM grounded action schema, deterministic guidance, transactional runtime persistence, typed API, and direct React profile/form/result routes without personal/watch coupling.
- 2026-07-10: Focused target/model tests pass 34/34, related API regressions pass 76/76, browser gate passes 110/110 plus typecheck/build/bundle audit, MyPy passes 84 files, and complete network-disabled Python suite passes 338/338 with 86.45% coverage and three snapshots. Evidence: `.10x/evidence/2026-07-10-target-bird-planning.md`.
- 2026-07-10: Review repair rejects all candidate-dependent actions for empty evidence before persistence; supplies the GLM complete bounded candidate/origin/freshness/weather facts protected by an exact canonical SHA-256 grounding echo; normalizes strict available/partial/unavailable weather before synthesis/persistence; and hardens server/browser weather, unit, timestamp, distance, duration, freshness, action, and error relationships. Weather results now render retrieval time and every normalized metric with source units. Focused model/target tests pass 40/40, related backend tests pass 84/84, the complete network-disabled Python suite passes 344/344 at 86.42% coverage, and the complete browser gate passes 121/121 plus typecheck/build/bundle audit.
- 2026-07-10: Final route-semantics repair sends saved-plan users back to the encoded species profile through native navigation and distinguishes focused load/replay unavailable errors from focused create errors. Six target component tests and the complete 122-test browser/typecheck/build/bundle gate pass.
- 2026-07-10: Final independent review passed with no blocker. Review: `.10x/reviews/2026-07-10-target-bird-planning-review.md`.
- 2026-07-10: Retrospective preserved honest-empty action constraints, complete canonical evidence grounding, and pre-persistence weather normalization in strict schemas and adversarial tests; no additional skill record is needed.

## Blockers

None.
