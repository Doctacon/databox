Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/2026-07-11-migrate-catalog-and-map-curated-photos.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Catalog photo live resume timeout checkpoint

## What was observed

The explicitly authorized live resume command was launched exactly once. The execution harness terminated the tool invocation at its 3,600-second timeout before the command returned a result. Per the ticket contract, the command was not restarted and no manual SQL or counter manipulation was performed.

The durable checkpoint after termination has exactly 456 valid current curated rows and 250 missing current identities. Provider/status counts are 373 available `inaturalist` rows and 83 unavailable `curated_photo` rows. The existing run `catalog_photo_2b8741d643ec4f97a8f566ee1a79b943` is durably `status=running`, `target_taxa_count=706`, `processed_taxa_count=456`, `lookup_count=1223`, and `safe_failure=NULL`. This is a monotonic increase of 145 completed identities and 145 lookups from the preflight checkpoint of 311/1078.

No process held `data/databox.duckdb` after termination. DuckDB left the newly committed state in `data/databox.duckdb.wal`; the base database file remains identical to the protected preflight copy.

## Preflight evidence

- Corrected gate: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='--no-cov' .venv/bin/pytest -q -p no:cacheprovider tests/test_curated_photo.py tests/test_catalog_media.py` — 43 passed.
- Focused MyPy passed both implementation modules; Ruff check and format check passed all four implementation/test files; `git diff --check` passed; the staged-file list was empty.
- Provider prerequisites returned `{"xeno_canto_api_key_configured": true}` without exposing secrets.
- `lsof data/databox.duckdb` reported no open handle immediately before launch; no Quack, SQLMesh, catalog-media, source-refresh, or parallel-refresh writer was active.
- Read-only semantic snapshot: catalog 706, exactly 311 valid current curated rows, exactly 395 missing; counts were 228 available `inaturalist` and 83 unavailable `curated_photo`; run metadata was failed/311 processed/1078 lookups/`KeyboardInterrupt`.
- Preflight warehouse SHA-256: `da98954d69901d56584fae05e1c159027a9e7cdba8435b7f8b8e4f6b7a8cd7c1`.
- Protected copy `/tmp/databox-before-catalog-photo-resume.duckdb` had the same SHA-256.
- Completed preflight identity-set SHA-256: `a894c873fd8a0bdfdd6ab662063227b28fbff45566171a8d1443f2f0b5fb4db8`.
- `/tmp/catalog-photo-pre.json` captured 86 protected table/subset fingerprints, including every table other than expected-mutating catalog photo results/run state plus a separate exact call-row fingerprint. `/tmp/catalog-photo-external-pre.sha256` captured 19 non-warehouse data files.

## Exact live command and outcome

```text
.venv/bin/python scripts/catalog_media.py --refresh-photos --batch-size 706
```

The tool outcome was `Command timed out after 3600 seconds`. There was no completion JSON. The command was not polled while running and was not rerun.

## Durable checkpoint validation

`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/catalog_photo_state_snapshot.py data/databox.duckdb /tmp/catalog-photo-failure-checkpoint.json` observed:

- catalog count: 706;
- valid current curated count: 456;
- missing current count: 250;
- provider/status: `inaturalist:available=373`, `curated_photo:unavailable=83`;
- checkpoint completed-identity-set SHA-256: `07fd1edcb1b7596ed33474679ae9f60b2c5437d12563cf4d1009fed4421dab81`;
- all 86 protected table/subset fingerprints equal their preflight values, with no missing fingerprint.

Therefore catalog facts, call rows and catalog-media non-photo runs, observations/personal/Watches, calendar/outbox, refresh/runtime settings, raw source state, SQLMesh models/state tables, planner state, AVONET, and all other protected warehouse tables remained unchanged through the checkpoint. Non-warehouse files were unchanged except for the expected new DuckDB WAL file.

Exact storage hashes at checkpoint:

- base `data/databox.duckdb`: `da98954d69901d56584fae05e1c159027a9e7cdba8435b7f8b8e4f6b7a8cd7c1`;
- protected base copy: `da98954d69901d56584fae05e1c159027a9e7cdba8435b7f8b8e4f6b7a8cd7c1`;
- `data/databox.duckdb.wal`: `9337cc8bfebb02829ee1e205a20382515f7dfcbf035f434c7af71594ba206e4c`.

## Limits and required next action

This is a failed/interrupted checkpoint, not completion evidence. The required 706 valid current rows, zero remaining, final provider/status counts, final post hashes, and completion/no-op assertions are not satisfied. The run metadata remains `running` because external timeout termination did not pass through the Python failure handler. Do not manually alter it and do not automatically rerun. A fresh operator decision and execution window longer than one hour are required before resuming the 250 missing identities.
