Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Relates-To: .10x/tickets/done/2026-09-03-prune-rufous-from-databox.md

# Rufous implementation pruning evidence

## Deletion and retained boundaries

Deleted the verified product-owned React app, AI worker, FastAPI/agent/state/media/public Python modules, product scripts/tests/config/migrations/infra/workflows/docs, `birding_agent` and `rufous_public` models/contracts/tests, and Rufous iNaturalist provider/tests. Removed the target-bearing USFWS Dagster domain and active source-registry entry while retaining the isolated public `databox_sources.usfws` package and its complete cassette-backed tests.

Retained `databox.product_artifact`, its twelve-relation frozen export contract and tests, all required environmental and source inputs, all `environmental_observations` models, and `analytics.platform_health`. Generated platform health now covers only seven actively orchestrated Databox sources. Generated dictionary/lineage now contains thirteen retained models.

Removed product Task targets, frontend CI job/path classifier, DeepEval/AI/FastAPI/media dependencies, Cloudflare/SMTP settings, and stale product docs. Renamed the retained shared refresh Dagster job from `parallel_quack_*` to `parallel_iceberg_*` and removed watched-bird evaluation coupling.

## Validation

- Full Databox pytest after core pruning: 393 passed, 85.51% coverage.
- Retained SQLMesh: 7/7 passed. A stale moved test warning was then eliminated by deleting its remaining file.
- Post-reconciliation focused tests: 64 passed (settings/source CI/source registry/analytics inventory), then 59 passed (parallel refresh/source registry/source CI).
- Ruff and format passed; MyPy passed across 90 source files.
- MkDocs strict passed after regenerating 13 model pages, index, and lineage.
- Pre-commit passed all hooks; secret scan passed across 778 eligible files; diff check passed.
- `uv lock`/`uv sync --locked` removed 29 product-only transitive packages.

## Standalone verification

Rufous's immutable remote Git dependency resolved with `uv sync --extra r2 --locked`. Aggregate pytest reached 1,063 passes, then failed one branding assertion because transferred `docs/rufous-operations.md` contained the product name `Databox` in user-visible operations text. The recovery pass replaced that stale wording with `upstream data-platform checkout`; the exact failing test now passes (1/1), Rufous `uv lock --check` passes, and Rufous `git diff --check` passes. The complete Rufous aggregate was not rerun during the bounded recovery pass.

## Recovery validation

- Inspected the existing 382-file partial diff before editing; did not redo deletion work.
- Focused retained Databox tests passed 66/66: repository layout, artifact exporter, source registry/CI, and analytics inventory.
- Databox `uv lock --check`, Dagster `Definitions` import, SQLMesh 7/7, residue scan, and `git diff --check` passed.
- An exploratory call to nonexistent Dagster `Definitions.get_all_job_defs()` failed with `AttributeError`; the supported definitions import then passed. This was a validation-command error, not a repository defect.
- No files are staged in either repository.
- Full Databox CI, strict docs, Ruff, MyPy, pre-commit, and full Rufous aggregate were not rerun in this bounded recovery; earlier successful outputs above remain the available evidence.

## Review status

Implementation is intentionally uncommitted and ticket remains open for independent review. No known focused validation blocker remains; full cross-repository acceptance still requires the explicitly not-rerun aggregate gates.
