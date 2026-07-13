Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: `.10x/tickets/2026-07-12-harden-trip-planner-curated-photo-resume.md`, planner media enrichment/backfill/API repair and focused tests
Verdict: pass

# Trip Planner curated-photo activation and resume self-review

## Assumptions tested

- Injecting a GBIF getter cannot restore GBIF representative-photo authority.
- GBIF occurrence context and Xeno-canto call evidence remain separate from representative-photo activation.
- Provider name and singleton cardinality alone cannot mark malformed or wrong-species curated metadata complete.
- A lookup or insertion failure after one completed recommendation does not erase that checkpoint or repeat it on rerun.
- GET serialization performs offline validation only and fails legacy representative evidence unavailable.

## Findings

No blocker or significant finding remains in this ticket's bounded surface.

- New photo selection unconditionally uses the shared curated selector. The old GBIF helper remains only as non-authoritative legacy utility coverage and cannot be reached through `enrich_recommendation_media`.
- The API has one active representative-photo branch: validated Wikimedia/iNaturalist metadata. Other persisted sources return typed unavailable evidence.
- `_inspect` reconstructs summary, payload, source identity, caveats, retrieval time, and exact recommendation name into `CuratedPhotoResult` and uses `curated_photo_result_is_safe` before considering a row complete.
- Photo lookup is performed for one recommendation, followed immediately by a transaction that replaces/inserts that recommendation's row. Tests prove lookup- and persistence-interruption resume behavior.
- Focused tests use deterministic curated fixtures, preserve occurrence context/calls, and execute without live network or project database mutation.

## Verdict

Pass. The ticket's backend activation, offline completion validation, and resume findings are resolved with focused test and static evidence.

## Residual risk

The full repository and API regression suites, frontend gates, and final read-only runtime-state inspection remain owned by aggregate verification. Provider-hosted images may later become unavailable; no binaries are stored.
