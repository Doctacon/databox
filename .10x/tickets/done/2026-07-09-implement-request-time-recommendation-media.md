Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-add-recommendation-card-photos-and-calls.md
Depends-On: None

# Implement request-time recommendation media enrichment

## Scope

Implement `.10x/specs/recommendation-media-enrichment.md` in the Python planner/API and DuckDB persistence boundary.

Required work:

- add bounded server-side GBIF exact-species Arizona still-image lookup,
- add bounded server-side Xeno-canto exact-species Arizona lookup with global fallback,
- perform enrichment only after recommendation identity/rank is fixed,
- deterministically select one eligible photo and one eligible call per recommendation,
- preserve creator/rights-holder/recordist, license, source identifiers/references, Arizona/global scope, selection reason, and lookup caveats,
- normalize upstream/timeout/malformed responses into safe typed unavailable states without failing the plan,
- enforce strict URL, identity, MIME/media type, species, and Creative Commons license validation,
- keep ND bytes unmodified and fail closed when an exact original URL is not explicitly safe,
- persist exactly one recommendation-linked photo result and call result, including unavailable states, in the single DuckDB,
- expose stable recommendation-centric `photo` and `call` response objects,
- persist a bounded aggregate tool trace without credentials or raw transport details,
- preserve atomic plan cleanup and existing Cloudflare grounding behavior,
- add deterministic fixtures/tests for Queen Valley coverage, Arizona preference, global fallback, candidate ranking, licenses, URL/identity attacks, partial failures, persistence/reload, duplicate protection, and zero ranking/model changes.

## Explicit exclusions

- No React layout work beyond any minimal generated/shared type contract needed by the API.
- No browser discovery calls.
- No image/audio binary download, proxy, storage, cache, crop, transform, waveform, or transcoding.
- No Wikimedia integration.
- No model prompt/output changes or media-driven recommendation changes.
- No existing-plan mutation in this ticket.

## Acceptance criteria

- Each newly created recommendation persists one photo result and one call result with status available or unavailable.
- Exact Queen Valley fixture coverage produces valid photo/call results for all eight species, with Ross's Goose and American White Pelican calls labeled global and local-capable species preferring Arizona.
- GBIF candidates require exact normalized species identity, eligible Creative Commons license, attribution, supported image media, and safe URL/source relationships.
- Xeno-canto candidates retain canonical ID and exact safe source/audio relationships plus deterministic type/quality/ID ranking.
- Timeout, malformed, unavailable, unlicensed, unsafe, or absent media creates a durable unavailable result but does not fail or alter the plan.
- API reload returns identical typed recommendation media from persisted DuckDB data without network access.
- No browser configuration, credential, raw arbitrary URL, or binary media enters committed assets.
- Focused Ruff/MyPy/tests, planner/API integration, DeepEval, full CI, docs, secret checks, and independent review pass.

## Evidence expectations

Record upstream fixtures, selection/cardinality assertions, persistence and no-side-effect tests, security/license matrix, exact commands/results, limits, and independent review.

## Progress and notes

- 2026-07-09: Added `recommendation_media.py` with fixed HTTPS endpoints, one-MiB/10-second transport limits, 50-candidate bounds, injected independent GBIF/Xeno getters, exact normalized binomial matching, strict Creative Commons/attribution/MIME/URL validation, deterministic selection, Arizona-first Xeno lookup, and typed unavailable results.
- 2026-07-09: Replaced the scheduled multi-row Xeno planner step with bounded request-time enrichment after ranking. The planner persists exactly one recommendation photo/call row per recommendation, validates cardinality before its existing transaction, keeps media outside model grounding, and records a safe aggregate trace.
- 2026-07-09: Added recommendation-centric typed `photo` and `call` API responses reconstructed from persisted rows. Reload is read-only/network-free; existing rows are not backfilled.
- 2026-07-09: Added Queen Valley eight-species, selection-order, Arizona/global fallback, license, URL/identity attack, timeout/malformed, response-bound, persistence/reload, rerun-duplicate, rank/model-invariance, API, and DeepEval coverage.
- 2026-07-09: Focused Python validation passed 36 tests; frontend passed typecheck, 27 tests, and production build; DeepEval passed 2 tests; full CI passed 222 tests at 83.49% coverage; bundle audit and strict docs build passed.
- 2026-07-09: Evidence recorded at `.10x/evidence/2026-07-09-request-time-recommendation-media.md`. Ticket remains active pending independent review.
- 2026-07-09: Independent review found six blockers: generic CC acceptance, unsafe/general photo URLs, incomplete ranking tie-breaks, query-only geography trust, retained transport exception context, and an incorrect Queen Valley species fixture.
- 2026-07-09: Repaired all six blockers with an explicit CC family/version matrix; photo-ND fail-closed behavior; exact verified GBIF 500x500 cache key/MD5 paths; total immutable-field ranking; returned-candidate Arizona validation; cause/context-free transport errors; and the exact researched eight-species Queen Valley fixture.
- 2026-07-09: Repair validation passed 53 focused Python tests, 2 DeepEval tests, 27 frontend tests/typecheck/build, bundle audit, strict docs, and full CI with 239 tests at 83.90% coverage. Ticket remains active for independent re-review.
- 2026-07-09: Final re-review found one remaining Xeno tie: casefold-equivalent persisted output spellings could still depend on input order. Added exact case-sensitive output fields after normalized rank fields and reversal coverage for `Alice`/`ALICE`, `Call`/`CALL`, and `Arizona`/`ARIZONA`; full selected objects are identical. Final focused validation passed Ruff, MyPy, 28 media tests, and diff/no-stage checks.
- 2026-07-09: Independent final review passed all execution, persistence, licensing, URL, geography, transport-safety, Queen Valley, and total-order criteria. Review: `.10x/reviews/2026-07-09-request-time-recommendation-media-review.md`.
- 2026-07-09: Retrospective: media metadata must be validated as a cross-field identity/license/geography contract, and deterministic selection must totally order the exact persisted object rather than only normalized semantic fields. The focused selector and adversarial reversal tests preserve these lessons; no separate knowledge/skill record is needed.

## Blockers

None.
