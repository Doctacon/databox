Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-evolve-product-into-rufous.md
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

## Blockers

None.
