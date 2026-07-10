Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-add-recommendation-card-photos-and-calls.md
Depends-On: .10x/tickets/done/2026-07-09-implement-request-time-recommendation-media.md, .10x/tickets/done/2026-07-09-integrate-media-into-recommendation-cards.md, .10x/tickets/done/2026-07-09-backfill-existing-plan-media.md

# Verify recommendation-card media

## Scope

Perform aggregate verification and adversarial closure review for request-time media enrichment, recommendation-card presentation, and existing-plan backfill. This ticket verifies and records; it does not silently repair child defects.

## Acceptance criteria

- Every parent/child criterion maps to durable evidence.
- A deterministic new plan proves recommendation identity/rank is fixed before media and remains unchanged under available/unavailable lookup outcomes.
- Exact GBIF photo and Xeno-canto Arizona/global call selection, licensing, attribution, deterministic ranking, URL safety, timeouts, concurrency bounds, and unavailable states are covered.
- The backfilled Queen Valley plan reloads with one photo result and one call result per card from DuckDB only.
- No GET endpoint causes a discovery request or write.
- Card order, placeholders, attribution, native media semantics, section order, final Evidence/Workflow disclosure, and absence of the standalone media section are verified accessibly.
- No image/audio binary, credential, arbitrary URL, or browser discovery configuration appears in the repository/bundle/warehouse.
- Scheduled Quack sources remain independently runnable and the single-DuckDB architecture is unchanged.
- SQLMesh/warehouse, planner/API, DeepEval, frontend, CI, docs, pre-commit, secret, bundle, and media-artifact checks pass.
- Independent aggregate review returns pass or every finding has a durable owner.

## Required checks

At minimum run repository equivalents of:

- deterministic GBIF/Xeno client and selection tests,
- planner/API persistence/reload/failure/atomicity tests,
- GET no-network/no-write tests,
- backfill dry-run/apply/second-run and immutable-plan assertions,
- React typecheck/all tests/build plus rendered accessibility/order/security assertions,
- full CI, strict docs, pre-commit, bundle/secret scan,
- tracked/untracked binary-media audit,
- production warehouse cardinality and record-graph/reference checks.

Live probes MUST be bounded to the minimum needed, MUST NOT print credentials, and MUST NOT retry or weaken validation after failure.

## Evidence expectations

Create aggregate evidence with exact commands, outputs, criterion mapping, limits, and a final independent review. Reconcile all child/parent statuses and perform retrospective extraction before closure.

## Progress and notes

- 2026-07-09: Read the parent, all three done children, both focused specs, all child evidence, and all three pass reviews; focused graph/status/reference checks are coherent.
- 2026-07-09: Deterministic media/planner/API/backfill/Quack/source checks passed 100 tests. Source inspection and planner tests prove rank is fixed before media, model grounding receives core evidence only, and media/cardinality are included before completed-plan persistence and cleanup.
- 2026-07-09: Current backfill dry-run and apply are both zero-target, zero-write, zero-lookup no-ops; no live media or Cloudflare discovery occurred.
- 2026-07-09: Read-only warehouse/API verification found 2 plans, 16 recommendations, exactly 16 available photos and 16 available calls, zero bad cardinality, Queen Valley 8/8 cards available/available, canonical GBIF/Xeno identities/licenses/active URLs, zero binary columns, and zero GET discovery/write with unchanged full-table snapshot hash.
- 2026-07-09: SQLMesh passed 11 tests with no prod diff. React strict TypeScript, all 50 tests, 30-module build, and bundle audit passed. DeepEval passed 2 tests. Full CI passed 258 tests at 84.09% coverage. Strict docs, pre-commit, secret/binary/browser-discovery, Quack architecture, graph/reference, diff, and no-stage checks passed.
- 2026-07-09: Aggregate evidence recorded at `.10x/evidence/2026-07-09-recommendation-card-media-aggregate-verification.md`.
- 2026-07-09: Independent aggregate review mapped every criterion, accepted `United States of America` as the exact US synonym under the existing contract, and returned pass with no unowned defect. Review: `.10x/reviews/2026-07-09-recommendation-card-media-aggregate-review.md`.
- 2026-07-09: Retrospective: verification exposed no new procedure beyond child lessons. The only diagnostic was a raw-versus-normalized species comparison in the read-only verifier; applying the same authority-free binomial normalizer corrected the assertion without product mutation. Aggregate evidence records the distinction; no separate knowledge/skill record is needed.

## Blockers

None.
