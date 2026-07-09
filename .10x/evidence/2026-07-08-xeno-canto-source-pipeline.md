Status: recorded
Created: 2026-07-08
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-08-add-xeno-canto-source-pipeline.md

# Evidence: Xeno-canto source pipeline

## What was observed

A Xeno-canto source pipeline was added for bird-sound recording metadata used by the Birding Trip Copilot. The integration uses Xeno-canto API v3 metadata responses, preserves media links/license/provenance fields, and does not download or store audio files.

## Procedure and results

1. Implemented source and orchestration wiring:

   - `packages/databox-sources/databox_sources/xeno_canto/source.py`
   - `packages/databox-sources/databox_sources/xeno_canto/config.yaml`
   - `packages/databox/databox/orchestration/domains/xeno_canto.py`
   - `Source(name="xeno_canto", raw_tables=("recordings",))`
   - `raw_xeno_canto.recordings` Quack dedupe key on `id`
   - `xeno_canto_ingest` and `xeno_canto_daily_pipeline` Dagster jobs

2. Added tests:

   ```bash
   .venv/bin/python -m pytest --no-cov \
     packages/databox-sources/tests/xeno_canto \
     tests/test_source_registry.py \
     tests/test_motherduck_autocreate.py -q
   ```

   Result:

   ```text
   20 passed, 11 warnings
   ```

3. Verified source layout and generated operational platform-health SQL coherence:

   ```bash
   .venv/bin/python scripts/check_source_layout.py
   .venv/bin/python scripts/generate_platform_health.py --check
   ```

   Results:

   ```text
   6 ok · 0 skipped · 0 failing (of 6)
   transforms/main/models/analytics/platform_health.sql matches source registry.
   ```

4. Verified formatting/linting/Dagster definitions/type-checking for affected files:

   ```bash
   .venv/bin/ruff check <affected files>
   .venv/bin/ruff format --check <affected files>
   .venv/bin/dg check defs --use-active-venv
   .venv/bin/mypy packages/databox-sources/databox_sources/xeno_canto \
     packages/databox/databox/orchestration/domains/xeno_canto.py
   ```

   Results:

   ```text
   Ruff: All checks passed.
   Ruff format: 9 files already formatted.
   Dagster: All definitions loaded successfully.
   mypy: Success: no issues found in 3 source files.
   ```

5. Verified Quack-backed dlt ingestion with a mocked Xeno-canto API response because no local `XENO_CANTO_API_KEY` was present for live smoke:

   ```bash
   DATABOX_BACKEND=quack XENO_CANTO_API_KEY=test-key \
     .venv/bin/python <mocked xeno_canto_source quack smoke script>
   ```

   Result:

   ```text
   rows=1
   relations=[('raw_xeno_canto', '_dlt_loads', 'BASE TABLE'), ('raw_xeno_canto', '_dlt_version', 'BASE TABLE'), ('raw_xeno_canto', 'recordings', 'BASE TABLE')]
   main_dlt_relations=0
   ```

6. After the user added `XENO_CANTO_API_KEY` to local `.env`, verified live Xeno-canto ingestion through Dagster/Quack without printing or recording the key:

   ```bash
   # .env was sourced without echoing secrets.
   DATABOX_BACKEND=quack DATABOX_SMOKE=1 \
     .venv/bin/dg launch --target-path packages/databox --job xeno_canto_ingest
   ```

   Result:

   ```text
   run_id=4cc58188-a7bd-4ae6-92fa-188e94cd8be7
   RUN_SUCCESS
   raw_xeno_canto.recordings rows=5
   raw_xeno_canto._dlt_loads BASE TABLE
   raw_xeno_canto._dlt_version BASE TABLE
   main._dlt* relations=0
   sample licenses=https://creativecommons.org/licenses/by-nc-sa/4.0/
   ```

7. Verified the full smoke pipeline after repairing SQLMesh prod restatement for newly added models:

   ```bash
   task verify
   ```

   Result:

   ```text
   .logs/verify-20260708-203153.log
   task verify: passed
   raw_xeno_canto.recordings=5
   birding_agent.xeno_canto_media_evidence=5
   birding_agent.species_lookup=17896
   main._dlt* relations=0
   ```

## What this supports

- `xeno_canto` is a registered Databox source with matching Dagster domain wiring.
- Local Quack-backed dlt ingestion can create physical `raw_xeno_canto` tables with dlt metadata in the raw schema.
- The source preserves recording IDs/URLs, species names, quality fields, date/location metadata, license fields, attribution, and provenance fields.
- Source layout, platform-health codegen, targeted tests, Dagster definitions, and targeted type-checking pass.

## Limits

- Live Xeno-canto smoke was run only in `DATABOX_SMOKE=1` mode, yielding 5 rows.
- The source stores metadata and media links only. It intentionally does not download audio files.
- No planner/CDM SQLMesh models were added in the source ticket; planner SQL interfaces were added later under `.10x/tickets/done/2026-07-08-model-birding-planner-sql-interfaces.md`.
