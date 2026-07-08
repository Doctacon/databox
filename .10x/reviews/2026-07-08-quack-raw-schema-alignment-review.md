Status: recorded
Created: 2026-07-08
Updated: 2026-07-08
Target: .10x/tickets/done/2026-07-08-align-quack-raw-schemas-with-dlt-datasets.md
Verdict: pass

# Review: Quack raw schema alignment

## Target

Working-tree changes for `.10x/tickets/done/2026-07-08-align-quack-raw-schemas-with-dlt-datasets.md`.

## Findings

### Pass: Quack dataset naming matches raw schemas

`settings.raw_dataset_name()` returns `raw_<name>` only when `DATABOX_BACKEND=quack` and preserves `main` for MotherDuck and legacy local backends.

### Pass: Quack still writes through the single local file

`settings.raw_catalog_path()` still routes Quack to `data/databox.duckdb`, and Quack credentials still attach through the Quack server rather than opening the file directly from dlt clients.

### Pass: Dedupe operates on physical raw tables

Post-load dedupe now targets `raw_<source>.<table>` base tables. Raw-view publishing was removed.

### Pass: legacy raw views are handled

The implementation drops old raw-schema views before starting the Quack server so dlt can create physical raw tables during migration. A targeted test verifies legacy views are dropped while base tables are preserved.

### Pass: local database inspection matches the requested mental model

A fresh `task full-refresh` produced raw source tables and dlt metadata as base tables under `raw_ebird`, `raw_noaa`, `raw_usgs`, and `raw_usgs_earthquakes`. No dlt-loaded source relations remained in `main`.

### Minor residual risk: MotherDuck not live-tested

MotherDuck and legacy local behavior are preserved by code and tests, but this review did not exercise a live MotherDuck run.

## Verdict

Pass.
