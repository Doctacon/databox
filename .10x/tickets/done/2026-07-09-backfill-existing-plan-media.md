Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-add-recommendation-card-photos-and-calls.md
Depends-On: .10x/tickets/done/2026-07-09-implement-request-time-recommendation-media.md, .10x/tickets/done/2026-07-09-integrate-media-into-recommendation-cards.md

# Backfill existing plan media

## Scope

Create and execute the explicit idempotent existing-plan media backfill governed by `.10x/specs/recommendation-media-enrichment.md`.

Required work:

- add a documented local command/task that opens the single DuckDB through the safe application lifecycle,
- enumerate existing recommendations missing photo/call results,
- run the same exact validated GBIF/Xeno-canto selection used for new plans,
- persist one photo and one call result per recommendation, including unavailable states,
- continue across per-species media failures with safe durable caveats,
- never call Cloudflare/the model,
- never alter plan text, recommendation identity/rank/group/rationale, weather, traces unrelated to media, or original creation timestamps,
- prove GET endpoints remain read-only and do not trigger backfill,
- run the command against the current local warehouse once after deterministic dry-run/tests,
- record before/after counts and Queen Valley card coverage without printing credentials.

## Explicit exclusions

- No background migration service or GET-side mutation.
- No plan regeneration.
- No recommendation/media binary storage.
- No mutation of raw source tables or SQLMesh models.
- No retries that hide persistent upstream invalidity.

## Acceptance criteria

- Before execution, the command reports a bounded target set without changing data.
- The current two-plan/16-recommendation baseline is reconciled against actual execution-time counts rather than hardcoded assumptions.
- After one run, every existing recommendation has exactly one photo result and one call result with available/unavailable status.
- A second run performs no duplicate inserts or substantive changes.
- Queen Valley reload uses only persisted media and performs no network call on GET.
- No model request, plan/rank/text/weather change, secret leak, binary artifact, or duplicate evidence is observed.
- Focused tests, dry-run/apply/idempotency evidence, warehouse assertions, docs, and independent review pass.

## Evidence expectations

Record pre/post row counts, immutable-plan field hashes, request counts/scopes, unavailable results, second-run no-op, exact commands/results, limits, and independent review.

## Progress and notes

- 2026-07-09: Added `databox.agent_tools.recommendation_media_backfill` and `task media:backfill -- --dry-run|--apply`. Dry-run opens the existing database read-only and performs no discovery; apply uses one DuckDB transaction and calls the shared validated selector without importing or invoking the planner/model path.
- 2026-07-09: Added deterministic coverage for dry-run, partial upstream failures, apply, second-run no-op, partial existing evidence, duplicate/cardinality protection, immutable plan/recommendation hashes, selective photo-only lookup, read-only/network-free GET, and no model invocation.
- 2026-07-09: Initial live dry-run reported 2 plans, 16 recommendations, 16 missing photos, 16 missing calls, and no duplicates. Initial apply persisted 16 available calls and 16 unavailable photos; inspection proved Xeno credentials/geography succeeded while GBIF returned exact candidates with `http://creativecommons.org/...` licenses and `country='United States of America'`.
- 2026-07-09: Canonicalized only exact recognized Creative Commons HTTP host/path licenses to their HTTPS forms and accepted the exact GBIF US country spelling alongside `US`/`United States`, retaining all finite license, species, state, attribution, URL, and cache-key/MD5 checks. A versioned one-time replacement path upgraded only exact defective `media_backfill_v2_` GBIF-unavailable rows with the original status/caveat and remains no-op after the reviewed selector version succeeds.
- 2026-07-09: Final live apply replaced all 16 photo rows with available results using 16 GBIF metadata lookups and no Xeno/model calls. The immediate second apply reported zero targets, inserts, replacements, and lookups. Warehouse verification found exactly one available photo and one available call for all 16 recommendations; all eight Queen Valley recommendations are available/available. An injected-network-failure GET returned 200 with zero discovery calls and an unchanged full application-table snapshot hash.
- 2026-07-09: Evidence recorded at `.10x/evidence/2026-07-09-existing-plan-media-backfill.md`.
- 2026-07-09: Review found the one-time repair predicate was broader than the actual defective prior run. Bounded it to exact `media_backfill_v2_` IDs plus the exact unavailable status and caveat; generic legacy, v1/unknown, v3/current, changed-caveat, and available rows are not retry targets.
- 2026-07-09: Added fault-injection coverage proving selector and mid-persistence failures roll back the full transaction, duplicate rows abort before discovery or writes, and an external-process DuckDB lock fails before mutation. Fourteen focused backfill tests pass. Current warehouse dry-run and apply remain zero-target/zero-lookup no-ops, so all 16 current v3 photo/call pairs were untouched.
- 2026-07-09: Independent final review passed dry-run, transaction/rollback, duplicate/lock, bounded v2 replacement, strict CC canonicalization, live 16/16 state, Queen Valley 8/8, no-model, and GET read-only criteria. Review: `.10x/reviews/2026-07-09-existing-plan-media-backfill-review.md`.
- 2026-07-09: Retrospective: live APIs can expose standards-compatible spelling/scheme variants absent from fixtures, but compatibility repairs must remain exact and version-bounded rather than becoming hidden retry policies. The HTTP-CC/country fixtures and v2-only repair tests preserve this lesson; no separate knowledge/skill record is needed.

## Blockers

None.
