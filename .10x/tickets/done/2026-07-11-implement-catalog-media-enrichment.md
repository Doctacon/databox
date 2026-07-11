Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-evolve-product-into-rufous.md
Depends-On: .10x/tickets/done/2026-07-09-build-arizona-bird-catalog-and-profile.md

# Implement catalog media enrichment

## Scope

Implement runtime catalog-media tables, explicit inspect/apply/refresh batch lifecycle, existing-selector reuse, checkpoints/resume/idempotency, and typed list/detail API media objects governed by `.10x/specs/arizona-catalog-media.md`.

## Acceptance criteria

- Exactly one photo and one call result per processed exact catalog species code; unavailable is explicit and never drops taxa.
- Exact identity, license, URL/hash, attribution, Arizona/global call scope, size/time bounds, and no-binary invariants reuse existing validators.
- Hybrids/taxonomy drift never use parent/historical/common-name guesses.
- Explicit batch is resumable, bounded, atomic per taxon, database-safe, inspectable, idempotent, and never runs from GET/startup/refresh.
- Catalog/profile GETs remain read-only/network-free and return unavailable when tables are absent/incomplete/stale.
- Strict API tests, lookup/VCR/fake-network tests, privacy/secrets/docs/full regressions pass.
- After independent review, one explicit live apply may populate current catalog metadata and must record aggregate coverage only.

## Explicit exclusions

No React presentation, binary storage/proxy/cache, scheduled job, parent fallback, new media provider, or automatic live apply before review.

## Evidence expectations

Record schema/checkpoints, selector reuse, identity/URL/license attacks, interruption/resume, zero-work second run, GET no-network/no-write, aggregate live coverage, and independent review.

## Progress and notes

- 2026-07-11: Added runtime result/run tables, bounded inspect/apply/refresh command, exact identity checkpoints, resumable refresh campaigns, idempotent apply, atomic per-taxon rollback, and selector reuse without binary storage.
- 2026-07-11: Catalog list/detail APIs now return strict photo/call objects and fail absent, incomplete, stale, wrong-source, or unsafe persisted metadata to typed unavailable without network or writes. Browser validators enforce exact media shapes and provider/license/identity/date boundaries; React presentation remains excluded.
- 2026-07-11: Focused media/API selector tests passed 56; complete network-disabled Python passed 432 at 86.71%; frontend passed 200 plus TypeScript/build/bundle; MyPy 92 files, secrets, hooks, docs freshness, MkDocs strict, Ruff, and diff gates passed.
- 2026-07-11: Live inspect found 706 targets, zero media tables/results/lookups, and identical before/after warehouse hash. No live apply or refresh ran. Evidence: `.10x/evidence/2026-07-11-catalog-media-enrichment.md`.
- 2026-07-11: Repaired review findings: apply now retains one durable running campaign across partial batches and completes only at zero remaining; a 706-taxon 250/250/206 regression proves cumulative target/processed status. Completion now validates the full source/kind/status/JSON/identity/license/URL result contract so corrupt rows are ordinary-apply targets. Catalog API downgrades unsupported photo formats and missing selection reasons. Boolean-only Xeno-canto prerequisite inspection is documented and missing configuration fails before writer/table creation. Final focused suite passed 56 and full network-disabled Python passed 432.
- 2026-07-11: Independent follow-up review passed and approved bounded live apply. The apply completed 706 exact taxa in 29 sequential batches under one durable completed run: photos 524 available/182 unavailable; calls 600 available/106 unavailable; zero remaining. A second apply had zero targets, processing, and lookups; read-only inspect matched all coverage. Review: `.10x/reviews/2026-07-11-catalog-media-enrichment-review.md`. Evidence: `.10x/evidence/2026-07-11-catalog-media-enrichment.md`.

## Acceptance mapping

- Exactly one photo and call result: live 1,412 rows span 706 distinct taxa with 706 complete result pairs.
- Identity/safety/no binary: existing selectors plus persisted-result validation cover exact identity, licenses, URL/hash, attribution, scope, size/time bounds, and metadata-only storage; adversarial tests and pass review confirm fail-closure.
- No fallback: hybrid and non-binomial tests perform zero lookup and persist unavailable without parent/history/common-name inference.
- Batch lifecycle: the 706-target regression and 29-batch live run prove durable resume, atomic taxon checkpoints, bounded sequential execution, final completion, and zero-work idempotency.
- Read boundary: absent/incomplete/stale/unsafe tests prove typed unavailable behavior; catalog GET hash/network tests prove read-only offline execution.
- Gates: 56 focused tests, 432 network-disabled Python tests, 200 frontend tests, MyPy, Ruff, secrets, hooks, docs, build, and bundle audit passed.
- Live apply: independent review passed before the one authorized live campaign; aggregate-only coverage and zero-work replay are recorded without sensitive values.

## Retrospective

Campaign completion must be defined against durable total targets rather than one process invocation. Checkpoint validity must include the complete safety contract, and external credentials must be checked before acquiring a writer. These invariants are now executable in the 706-target resume, corrupt-row repair, and missing-prerequisite tests.

## Blockers

None.
