Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/2026-07-12-harden-trip-planner-curated-photo-resume.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Trip Planner curated-photo activation and resume hardening evidence

## What was observed

Planner representative-photo enrichment now always enters the shared curated selector even when a legacy GBIF getter is injected. Persisted non-curated representative photos reduce to unavailable at the API boundary, while separately typed GBIF occurrence context remains untouched. Curated saved-photo completion now reconstructs the persisted result and applies the full offline validator against the exact recommendation scientific name. Photo lookup and persistence execute as one per-recommendation checkpoint, so an interruption retains prior completed recommendations and rerun queries only the unfinished recommendation.

## Procedure and results

- `pytest --no-cov -q tests/test_recommendation_media_backfill.py::test_apply_is_partial_failure_safe_idempotent_and_model_free`: 1 passed.
- `pytest --no-cov -q tests/test_recommendation_media.py tests/test_recommendation_media_backfill.py`: 50 passed in 2.95 seconds.
- The focused tests use a deterministic curated selector fixture and make no live provider calls.
- Adversarial coverage includes injected GBIF representative-photo rejection, call and GBIF occurrence-context preservation, malformed exact-species singleton repair, lookup interruption/resume without repeating the completed recommendation, persistence interruption with the prior checkpoint retained, idempotent rerun, duplicate/cardinality rejection, dry-run purity, model-free operation, and external DuckDB lock failure.
- `ruff format --check` on the three implementation files and three focused test files: passed (six files already formatted).
- `ruff check` on the same files: passed.
- `mypy` on `recommendation_media.py`, `recommendation_media_backfill.py`, and `api.py`: passed with no issues in three source files.
- `git diff --check`: passed.
- `git diff --name-only --cached`: empty.

No live provider, project DuckDB, model, email, source-refresh, call-refresh, or binary-media operation was run. Tests use temporary DuckDB files only.

## What this supports

This supports curated-only backend activation, full persisted-result validation against exact identity, per-recommendation resume checkpoints, preservation of non-photo evidence, deterministic no-network testing, and clean focused static gates.

## Limits

The parent aggregate verification owns the full Python/frontend suite and final live read-only state validation. Remote provider availability remains outside local control because Rufous persists metadata and bounded URLs rather than image binaries.
