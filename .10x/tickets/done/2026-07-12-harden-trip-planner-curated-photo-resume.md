Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`
Depends-On: `.10x/tickets/done/2026-07-11-migrate-trip-planner-curated-photos.md`

# Harden Trip Planner curated-photo activation and resume

## Scope

Make planner representative-photo activation curated-only at every backend boundary, validate persisted completion against exact recommendation identity and the full shared offline contract, and checkpoint provider lookups per recommendation so interruption does not repeat completed lookup work.

## Acceptance criteria

- New recommendation-photo enrichment always uses the shared curated selector; injected legacy GBIF seams cannot activate a GBIF representative photo.
- Persisted non-curated recommendation-photo evidence, including GBIF, reduces to unavailable; separately typed GBIF occurrence context remains available.
- Backfill completion is determined by reconstructing and validating the singleton persisted curated result against the recommendation's exact scientific identity, not provider name/cardinality alone.
- Lookup and persistence checkpoint per recommendation; interruption during provider lookup resumes without repeating previously completed lookups or duplicating evidence.
- Tests cover legacy GBIF rejection, occurrence-context preservation, malformed/stale curated singleton repair, exact identity mismatch, interruption during lookup, interruption during persistence, rerun no-op, and one-photo cardinality.
- No GET path discovers media or writes; no model, call lookup, email, refresh, or binary persistence occurs.
- Focused/full gates and read-only protected-state checks pass.

## Explicit exclusions

No recommendation regeneration, call enrichment changes, provider expansion, planner workflow redesign, or live backfill rerun unless another owning ticket explicitly requires controlled re-evaluation.

## Evidence expectations

Record adversarial backend tests, lookup counters across interruption/resume, before/after recommendation/non-photo evidence fingerprints, focused/full gates, and residual remote-availability limits.

## References

- `.10x/specs/superseded/curated-representative-bird-photos.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-architecture-review.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-correctness-review.md`
- `.10x/evidence/2026-07-12-trip-planner-curated-photo-migration.md`

## Progress and notes

- 2026-07-12: Opened from aggregate architecture/correctness review findings. No repair has begun.
- 2026-07-12: Implemented curated-only planner activation, full offline persisted-result validation against exact recommendation identity, and per-recommendation lookup/persistence checkpoints. Deterministic focused suites passed 50 tests; Ruff, formatting, targeted MyPy, diff checks, and empty staging passed. Evidence: `.10x/evidence/2026-07-12-trip-planner-curated-photo-resume-hardening.md`. Self-review: `.10x/reviews/2026-07-12-trip-planner-curated-photo-resume-self-review.md`.

## Blockers

None. Aggregate verification owns the full-suite and final runtime-state gates.
