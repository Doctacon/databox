Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Relates-To: .10x/tickets/done/2026-09-03-migrate-rufous-models-and-backend.md

# Rufous models and backend migration evidence

## Observed result

The standalone Rufous repository now owns its product models, backend, writable state, iNaturalist discovery, Iceberg publication helpers, and manual USFWS orchestration without private Databox imports or repository-relative Databox paths.

## Data/model boundary

All `birding_agent` and `rufous_public` upstream Databox relations now resolve through `databox_product.rufous_inputs_v1`. The consolidated eBird snapshot uses its contracted `order_1` taxonomy field and explicit UTC normalization. Rufous-owned `raw_inaturalist` remains local application/model state. Original `raw_*` strings remain only where model output records source provenance, not as query dependencies.

The independent SQLMesh configuration attaches `RUFOUS_DATABOX_PRODUCT_PATH` read-only and writes product models/state to the separate `RUFOUS_DATABASE_PATH`. Soda configuration targets that writable product database.

## Orchestration and ingestion

The manual unscheduled `usfws_ingest` multi-asset derives targets from `rufous_public.gbif_eod_occurrence`, imports `usfws_source` only from the pinned public `databox_sources.usfws` interface, and retains current-run/status publication behavior. iNaturalist is Rufous-owned and uses direct local dlt→DuckDB ingestion rather than private Databox/Quack helpers.

## Verification

- Full collection: 1,071 tests collected with no collection errors.
- In-scope Python aggregate excluding the web/deployment-owned workflow contract: 1,061 passed.
- Product SQLMesh: 11/11 passed. Supervisor confirmed the other seven of Databox's former aggregate 18 remain with Databox-owned models and must not be copied.
- Full destination targeted run: exactly five failures, all in `tests/rufous_media/test_rufous_public_workflow.py`, covering stale destination workflow commands and owned by `.10x/tickets/done/2026-09-03-migrate-rufous-web-public-deployment.md`; no test was weakened or globally skipped.
- Ruff and format passed for source/tests/config/scripts.
- MyPy passed for 53 source files.
- Secret scan passed for 261 eligible files.
- Pre-commit and `git diff --check` passed.
- Coupling search found no private `databox.*`, Polaris raw query, `DataboxSettings`, source-refresh backend, or `data/databox.duckdb` dependency in in-scope implementation.

## Limits

The web/public workflow remains copied but intentionally stale and production remains fail-closed. Its five preserved failures are the next ticket's executable contract. Independent acceptance review and destination commit remain pending.
