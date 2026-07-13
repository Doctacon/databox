Status: done
Created: 2026-07-13
Updated: 2026-07-13
Parent: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`
Depends-On: `.10x/tickets/done/2026-07-13-implement-inaturalist-only-representative-photos.md`, `.10x/tickets/done/2026-07-13-migrate-inaturalist-only-representative-photos.md`

# Harden iNaturalist photo operations and retry semantics

## Scope

Resolve final architecture/privacy review findings in the iNaturalist-only selector and migration operations: count actual v2/v1 HTTP attempts, persist bounded catalog and planner run observability, enforce the documented rate/day budget across local processes and restarts, distinguish retryable provider failures from terminal identity/no-eligible placeholders, provide governed photo-only retry behavior, and delete the now-unreachable GBIF representative-photo helper/seam.

## Acceptance criteria

- Selector results expose bounded actual request-attempt counts: zero for non-queryable identities, one when v2 fails, and two when v2 plus v1 are attempted.
- Catalog and saved-plan photo runs durably record run ID, status, target/checkpoint/processed counts, actual request attempts, provider/status/failure-class totals, start/end/duration, and bounded safe failure text.
- The <=60 requests/minute target and <10,000 requests/day cap are coordinated across local Rufous processes and survive restart using a minimal standard-library/open-source local mechanism with atomic locking; tests use isolated temporary state.
- Provider transport/throttle/schema/budget failures remain typed unavailable for presentation but are classified retryable and are not terminal completion checkpoints.
- Exact identity-invalid, non-binomial, and exhausted-curated-shortlist placeholders remain terminal.
- Explicit serialized photo-only retry resumes only retryable targets, preserves terminal/completed rows, calls no model/email/source/AVONET/call refresh, and becomes a network/write no-op after success.
- Catalog and planner interruption/retry tests prove exact request counts, checkpoints, failure classes, no duplicates, and no repeated completed requests.
- Dormant GBIF representative-photo selection helpers and unused injection seams are deleted; GBIF occurrence-context behavior remains.
- Focused/full Python and static/security gates pass without live provider or project DuckDB mutation.

## Explicit exclusions

No provider expansion, UI change, live migration repair, source/call refresh, model/email, binary media, or unrelated media refactor.

## Evidence expectations

Record schema/run examples with safe counts, isolated cross-process/restart budget tests, retryable-versus-terminal tests, deleted legacy surfaces, focused/full gates, and independent adversarial review.

## References

- `.10x/specs/curated-inaturalist-representative-bird-photos.md`
- `.10x/reviews/2026-07-13-inaturalist-only-final-architecture-review.md`
- `.10x/reviews/2026-07-13-inaturalist-only-final-privacy-security-source-review.md`

## Progress and notes

- 2026-07-13: Opened from final aggregate rereview findings. No repair has begun.
- 2026-07-13: Implemented durable 0/1/2 request-attempt accounting, atomic cross-process/restart rate state, retryable-versus-terminal classification, durable catalog/planner run observability, explicit retry/no-op behavior, and deletion of dormant GBIF representative-photo seams. Tests use isolated temporary limiter state; no live provider or project DuckDB mutation occurred.
- 2026-07-13: Focused selector/catalog/recommendation/backfill and occurrence-context checks passed (98); full Python passed (775, three snapshots, 86.44% coverage); targeted/full MyPy, Ruff/format, security/generated/docs/source-layout, 13 SQLMesh tests, all hooks, diff check, and empty staging passed. Evidence: `.10x/evidence/2026-07-13-inaturalist-photo-operations-hardening.md`. Independent adversarial self-review: `.10x/reviews/2026-07-13-inaturalist-photo-operations-hardening-review.md` (pass).
- 2026-07-13 retrospective: Persist request attempts immediately after transport returns rather than coupling them to evidence commit, because interruption is itself part of operational truth. Keep retryability in the strict persisted result so presentation can fail closed while completion logic remains operator-recoverable. Cross-process tests must always receive `tmp_path`; default durable rate state is production-only.

## Blockers

None. Acceptance criteria and review gate are satisfied.
