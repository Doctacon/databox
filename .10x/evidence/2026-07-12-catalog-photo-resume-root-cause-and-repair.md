Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/2026-07-11-migrate-catalog-and-map-curated-photos.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Catalog photo resume root cause and focused repair

## What was observed

Read-only inspection of `data/databox.duckdb` found one photo run, `catalog_photo_2b8741d643ec4f97a8f566ee1a79b943`, with `status=failed`, `target_taxa_count=706`, `processed_taxa_count=311`, `lookup_count=1078`, and `safe_failure=KeyboardInterrupt`. Its current photo rows are exactly 311: 228 available `inaturalist` rows and 83 unavailable `curated_photo` rows. The warehouse SHA-256 before and after this investigation/validation remained `da98954d69901d56584fae05e1c159027a9e7cdba8435b7f8b8e4f6b7a8cd7c1`.

`/tmp/catalog-photo-live.log` contains four summaries for the same run: two five-row observations followed by apparent 706-row completions at lookup counts 624 and 1050. The log is append-only command output and does not prove the later durable state.

## Root cause reconstruction

The prior worker transcripts provide direct evidence that state was manually destroyed between those logged completion snapshots:

- `.pi-subagents/artifacts/31b8e44c_worker_transcript.jsonl` records SQL that deleted the first five photo rows for this run and explicitly set `processed_taxa_count=0` and `lookup_count=0`.
- `.pi-subagents/artifacts/b368f860_worker_transcript.jsonl` records SQL after the first apparent completion that deleted 426 photo rows classified by caveat and explicitly set `processed_taxa_count=280`; after the second apparent completion it deleted another 423 rows and explicitly set `processed_taxa_count=283`.
- The next provider run was interrupted after 28 additional completed rows. This exactly reconciles durable `processed_taxa_count=311` (`283+28`) and `lookup_count=1078` (`1050+28`).

Therefore DuckDB did not spontaneously lose a completed transaction and the command did not automatically reset the run. The completed snapshots were subsequently invalidated by explicit operator SQL. Separately, source inspection found a real rerun defect: `run_catalog_photo_refresh` considered only rows with the selected run ID, and selected only running/failed runs. Invoking after a complete run therefore created a new run and re-queried every identity, replacing complete rows one by one.

## Repair observed

`run_catalog_photo_refresh` now derives completed checkpoints from strictly validated curated photo rows for every current catalog identity, independent of historical run ID. It returns immediately when all current identities are complete, without creating or updating a run or calling the selector. An interrupted/failed run targets only current identities lacking a valid curated result. Resume reconciliation is monotonic only; it never lowers a processed count, and it fails closed if durable processed metadata exceeds current validated results. Completion/remaining values are recomputed from validated current rows rather than trusted from stale counters. Provider lookup attempts retain the existing cumulative counter and completed current identities cannot increment it again.

The persistence transaction remains per missing target: only that target's prior photo is replaced alongside insertion and checkpoint increment. Complete and untouched rows are never selected for deletion.

## Deterministic validation

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='--no-cov' .venv/bin/pytest -q -p no:cacheprovider tests/test_catalog_media.py` — 17 passed. The interruption fixture proves the completed first identity remains curated, the two untouched identities retain their legacy rows, resume does not query the completed identity again, and lookup/process counters finish coherently. The complete-rerun fixture uses a getter that raises on any request and proves result rows and run rows are identical before and after the second invocation.
- `.venv/bin/ruff check packages/databox/databox/catalog_media.py tests/test_catalog_media.py` — passed.
- `.venv/bin/ruff format --check packages/databox/databox/catalog_media.py tests/test_catalog_media.py` — passed after formatting.
- `git diff --check` — passed.
- The accepted final static-typing repair explicitly narrows each `_safe_qid` result before adding it to `safe_ids: list[str]`; this preserves the existing accepted-ID set while making both `"|".join(safe_ids)` and `_entity_p225(..., qid)` statically safe.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='--no-cov' .venv/bin/pytest -q -p no:cacheprovider tests/test_curated_photo.py tests/test_catalog_media.py` — 43 passed (26 curated selector and 17 catalog media).
- `.venv/bin/mypy packages/databox/databox/curated_photo.py packages/databox/databox/catalog_media.py` — passed with no issues in both source files; the two reported selector errors are resolved.
- `.venv/bin/mypy packages/databox/databox` — reached all 56 package source files; the repaired modules passed, while the package-wide command remains environment-blocked by eight missing `databox_sources` import implementations in seven pre-existing orchestration-domain modules.
- `.venv/bin/ruff check packages/databox/databox/curated_photo.py packages/databox/databox/catalog_media.py tests/test_curated_photo.py tests/test_catalog_media.py` — passed.
- `.venv/bin/ruff format --check packages/databox/databox/curated_photo.py packages/databox/databox/catalog_media.py tests/test_curated_photo.py tests/test_catalog_media.py` — passed; all four files already formatted.
- `.venv/bin/python scripts/check_secrets.py` — exited successfully with `No files to check`, confirming the script requires explicit paths; `.venv/bin/python scripts/check_secrets.py packages/databox/databox/curated_photo.py` then passed the changed implementation file with no findings.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty.

## Independent review disposition

The accepted independent-review finding was limited to the two current MyPy errors at the `_safe_qid` boundary. The explicit narrowing resolves both without changing provider requests, ordering, filtering, persistence, or runtime values. Focused tests, module MyPy, Ruff, format, and diff gates pass. The review gate for this final typing-only repair is optional and no additional independent review was run in this worker; there are no known blockers from the accepted finding.

## Limits and residual state

No live provider lookup, migration/resume command, model, email, Quack/SQLMesh, AVONET/media request, image binary operation, or live DuckDB mutation was run. The live catalog remains intentionally incomplete at 311 current curated rows with 395 missing rows. The ticket remains active; completing those 395 rows requires separate explicit authorization.
