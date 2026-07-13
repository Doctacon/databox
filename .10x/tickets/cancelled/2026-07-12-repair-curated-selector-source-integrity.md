Status: cancelled
Created: 2026-07-12
Updated: 2026-07-13
Parent: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`
Depends-On: `.10x/tickets/done/2026-07-11-implement-curated-photo-selector.md`

# Repair curated selector source integrity

## Scope

Repair the source-selector defects identified by the aggregate privacy/security/source and architecture reviews: make real Commons thumbnails satisfy the <=1024 contract without accepting oversized images; prove exact P225 uniqueness independently of relevance-limited search; constrain redirects to approved origins; and add provider-attempt outcome/failure observability sufficient to explain source selection. Re-evaluate current catalog and saved-plan rows only after focused/full gates pass, using the already-authorized metadata-only migration boundaries and serialized DuckDB ownership.

## Acceptance criteria

- An eligible exact Wikimedia P225/P18 candidate is selected before iNaturalist when Commons returns its real provider thumbnail shape; iNaturalist is not called.
- The selected display URL remains provider-generated, exact-file-bound, HTTPS, and no wider than 1024 pixels.
- Exact-P225 resolution proves zero/one/multiple matches without relying on a relevance-limited first page; ambiguity fails closed before media or fallback activation.
- HTTP redirects are disabled or every hop/final URL is restricted to governed same-origin HTTPS endpoints; loopback, link-local, private, credential-bearing, HTTP, and unapproved targets fail closed.
- Run metadata records bounded attempted-provider outcomes/status/failure classes without raw provider payloads, secrets, or arbitrary URLs.
- Deterministic tests cover real 1280 Commons response behavior, out-of-window ambiguity, redirect attacks, source ordering, and observability.
- After preflight and protected-state fingerprints, current catalog and saved-plan photos are explicitly re-evaluated exactly once under the repaired selector; current valid rows reflect Wikimedia-first behavior and remain curated-or-placeholder.
- No model, email, source refresh, AVONET refresh, call enrichment, or binary download/storage occurs; protected personal/runtime/data state remains unchanged within recorded fingerprints.

## Explicit exclusions

No new providers, manual moderation UI, source refresh, call refresh, recommendation regeneration, or unrelated selector redesign.

## Evidence expectations

Record focused/full gate results, deterministic adversarial tests, bounded live metadata results, exact provider/status counts before and after re-evaluation, serialized-writer preflight, and protected-state fingerprints. Do not claim visual subject quality or future remote availability.

## References

- `.10x/specs/superseded/curated-representative-bird-photos.md`
- `.10x/decisions/inaturalist-curated-photo-api-split.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-privacy-security-source-review.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-architecture-review.md`
- `.10x/evidence/2026-07-12-curated-representative-photo-aggregate-verification.md`

## Progress and notes

- 2026-07-12: Opened from aggregate review findings. No repair has begun.
- 2026-07-12: Deterministic implementation phase completed: lower Commons provider tier with <=1024 activation validation, direct bounded exact-P225 SPARQL resolution, no-redirect/final-endpoint enforcement, and bounded atomic provider outcome counters. Focused Ruff/format and 55 curated/catalog tests pass. Evidence: `.10x/evidence/2026-07-12-curated-selector-source-integrity-deterministic-repair.md`. Self-review: `.10x/reviews/2026-07-12-curated-selector-source-integrity-deterministic-self-review.md`.
- 2026-07-12: An intermediate final test edit accidentally truncated `tests/test_catalog_media.py`; the 537-line repository base and the legitimate curated-photo tests were carefully reconstructed. Final focused tests prove the restored 788-line test file is coherent.
- 2026-07-12: All dependent repair tickets completed. Planner/API/CLI/catalog deterministic harnesses were repaired to use explicit curated transport and no-op test-only limiter injection, with a forbidden-live-network assertion. Focused 136 tests, full 786 tests/three snapshots/86.27% coverage, and all static/security/docs/SQLMesh/hooks/diff gates passed; the prior frontend evidence remains passing. Read-only preflight captured 86 protected fingerprints and 19 external hashes. The bounded live `Trogon elegans` confirmation then stopped unavailable because WDQS exact-P225 discovery timed out/failed; no iNaturalist fallback or DuckDB mutation occurred. Pre/post-probe protected state matched exactly. Evidence: `.10x/evidence/2026-07-12-curated-selector-live-provider-preflight-blocker.md`. Review: `.10x/reviews/2026-07-12-curated-selector-live-provider-preflight-review.md`.
- 2026-07-13: User authorized a retry. Fresh writer preflight and snapshots again found 706/706 valid catalog rows, eight/eight valid planner rows, 86 protected fingerprints, and 19 external hashes. Production-path `Trogon elegans` exact-P225 discovery again failed at WDQS, with Wikimedia-only attempted sources and zero iNaturalist calls. No apply command ran and the post-probe snapshot exactly matched preflight. Evidence: `.10x/evidence/2026-07-13-curated-selector-wdqs-retry-blocker.md`. Review: `.10x/reviews/2026-07-13-curated-selector-wdqs-retry-review.md`.
- 2026-07-13: Cancelled after the user superseded Wikimedia-first behavior with curated iNaturalist-only representative photos. Historical deterministic repairs and blocker evidence remain valid history; no Wikimedia re-evaluation will be attempted. Replacement work is owned by `.10x/tickets/done/2026-07-13-implement-inaturalist-only-representative-photos.md` and `.10x/tickets/done/2026-07-13-migrate-inaturalist-only-representative-photos.md`.

## Blockers

None. Cancelled as superseded scope.
