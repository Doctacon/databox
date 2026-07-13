Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Relates-To: `.10x/tickets/done/2026-07-13-harden-inaturalist-photo-operations.md`, `.10x/specs/curated-inaturalist-representative-bird-photos.md`

# iNaturalist photo operations hardening evidence

## What was observed

The curated iNaturalist selector now reports actual metadata-request attempts independently of selector lookup counts: zero for non-queryable identities, one for a v2-stage failure, and two when v2 plus v1 are attempted. Retryable budget, transport, and schema failures persist as strict typed unavailable results but do not become terminal completion checkpoints; exact identity failure, non-binomial identity, and exhausted curated shortlist remain terminal.

Catalog and saved-plan photo-only operations now persist bounded run records with run ID, running/failed/complete status, start/completion timestamps, duration, target/processed/checkpoint counts, selector lookup count, actual request count, bounded outcome/failure-class JSON, and safe failure. Explicit rerun targets only retryable results, preserves completed/terminal results, and becomes a network/write no-op after success.

The iNaturalist budget is coordinated through a standard-library `fcntl` lock plus atomically replaced bounded JSON state. The state survives process restart and serializes separate processes. Tests supply only temporary state paths; no `data/.inaturalist-photo-rate.json` or lock file was created.

Dormant GBIF representative-photo selection, cache-URL validation, helper functions, getter parameters, API/planner injection seams, and their positive tests were removed. Separately typed GBIF occurrence-context tools and tests remain and pass.

## Procedure and results

### Focused behavior

- Ruff formatting/check ran first on the scoped selector, catalog, recommendation media/backfill, planner/API, and test files and passed after two mechanical formatting fixes.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest --no-cov -x -q tests/test_curated_photo.py tests/test_catalog_media.py tests/test_recommendation_media.py tests/test_recommendation_media_backfill.py`: 96 passed.
- Focused selector/catalog/recommendation/backfill plus GBIF occurrence-context regression checks: 98 passed.
- Cross-process/restart budget tests use `tmp_path`, launch two separate Python processes against one temporary state file, reconcile the atomic count, and prove the durable daily cap after restart.
- Catalog retry coverage proves one v2 transport failure records one request, successful v2/v1 attempts record two, interruption after lookup retains attempts, retry targets only the failed identity, completed identities are not repeated, and the successful rerun is a no-op.
- Saved-plan coverage proves durable `birding_agent.recommendation_photo_runs` status, target/processed/lookup/request/outcome/failure/duration fields; retryable singleton replacement; exact two-stage request counts; no duplicates; and final no-op.
- `tests/test_birding_trip_planner.py::test_ranked_gbif_recommendations_keep_conformed_names_and_do_not_duplicate` and `tests/test_api.py::test_source_scientific_name_survives_lookup_persistence_and_api_reload` passed, preserving GBIF occurrence context independently of representative photos.

### Full gates

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest`: 775 passed, three snapshots passed, 86.44% coverage.
- Targeted MyPy on the six changed production modules passed after resolving the state-path union and optional DuckDB scalar result.
- Full `.venv/bin/mypy packages/`: 99 source files passed.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`: passed; 162 files formatted.
- Secret scan passed with no files requiring secret inspection.
- Staging and platform-health generated checks passed.
- `cd transforms/main && ../../.venv/bin/sqlmesh test`: 13 passed.
- Docs generation, strict MkDocs build, source-layout checks, and all 11 pre-commit hooks passed.
- `git diff --check` passed; cached/staged file list was empty.

## What this supports

This supports every owning-ticket acceptance criterion: exact request accounting, durable catalog/planner observability, cross-process/restart-safe budget enforcement, retryable-versus-terminal persistence semantics, explicit photo-only retry/no-op behavior, removal of dormant GBIF representative-photo seams, preservation of occurrence context, and complete deterministic/full validation without live provider or project DuckDB mutation.

## Limits

The file-lock mechanism coordinates processes sharing the same local filesystem and configured state path; it is not a distributed multi-host rate limiter. A reserved request remains conservatively counted if a process exits before transport. Provider-hosted images and schemas remain remote and may later change. No live provider request, project database write, physical-browser session, or assistive-technology session was performed in this ticket.
