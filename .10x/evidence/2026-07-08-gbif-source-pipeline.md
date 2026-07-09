Status: recorded
Created: 2026-07-08
Updated: 2026-07-08
Relates-To: .10x/tickets/done/2026-07-08-add-gbif-source-pipeline.md

# Evidence: GBIF source pipeline

## What was observed

A first GBIF source pipeline was added for the Birding Trip Copilot data-integration slice. The pipeline uses the public GBIF occurrence search endpoint and does not require credentials for the implemented endpoint.

The implementation lands bird occurrence records in `raw_gbif.occurrences`, preserves GBIF identifiers/taxonomy/location/status/provenance fields, wires the source into Dagster definitions and source registry, and keeps source domains ingestion-only. No CDM/planner SQLMesh models were added.

A supervisor scope clarification allowed updating only generated operational `analytics.platform_health` SQL and its Soda source valid-values contract as a necessary consequence of adding `gbif` to the source registry. No planner/CDM SQLMesh models were changed.

## Procedure and results

### Focused static checks

```bash
.venv/bin/ruff check packages/databox-sources/databox_sources/gbif packages/databox-sources/tests/gbif packages/databox/databox/orchestration/domains/gbif.py packages/databox/databox/orchestration/definitions.py packages/databox/databox/config/sources.py packages/databox/databox/destinations/quack.py tests/test_motherduck_autocreate.py
.venv/bin/ruff format --check packages/databox-sources/databox_sources/gbif packages/databox-sources/tests/gbif packages/databox/databox/orchestration/domains/gbif.py packages/databox/databox/orchestration/definitions.py packages/databox/databox/config/sources.py packages/databox/databox/destinations/quack.py tests/test_motherduck_autocreate.py
.venv/bin/mypy packages/databox-sources/databox_sources/gbif packages/databox/databox/orchestration/domains/gbif.py
```

Results:

```text
ruff check: All checks passed
ruff format --check: 9 files already formatted
mypy: Success: no issues found in 3 source files
```

### Focused tests

Initial focused pytest without `--no-cov` passed all selected tests but failed the repository-wide coverage threshold because only a subset was executed. The focused tests were rerun with coverage disabled:

```bash
.venv/bin/pytest --no-cov packages/databox-sources/tests/gbif/test_resources.py tests/test_source_registry.py tests/test_motherduck_autocreate.py
```

Result:

```text
18 passed, 11 warnings
```

### Source layout

```bash
.venv/bin/python scripts/check_source_layout.py
```

Result:

```text
  ✓ ebird
  ✓ gbif
  ✓ noaa
  ✓ usgs
  ✓ usgs_earthquakes

5 ok · 0 skipped · 0 failing (of 5)
```

### Operational platform health codegen

```bash
.venv/bin/python scripts/generate_platform_health.py --check
```

Result:

```text
transforms/main/models/analytics/platform_health.sql matches source registry.
```

### Dagster definition load

```bash
.venv/bin/dg check defs --use-active-venv
```

Result:

```text
All definitions loaded successfully.
```

### Quack-backed GBIF ingestion

A temp-database validation proved the source can create physical raw GBIF tables through Quack without relying on the user's local warehouse state:

```bash
# summarized command: start a Quack ingest session against a temp DuckDB file,
# run dlt pipeline gbif_validation with dataset_name=raw_gbif and gbif_source(max_records=5),
# then inspect information_schema after Quack stops.
```

Result:

```text
rows=5
relations=[
  ('raw_gbif', '_dlt_loads', 'BASE TABLE'),
  ('raw_gbif', '_dlt_version', 'BASE TABLE'),
  ('raw_gbif', 'occurrences', 'BASE TABLE')
]
```

A live smoke Dagster source job also succeeded after clearing an intermediate `raw_gbif` schema created before the GBIF column hints were finalized:

```bash
DAGSTER_HOME="$PWD/.dagster" DATABOX_BACKEND=quack DATABOX_SMOKE=1 \
  .venv/bin/dg launch --target-path "$PWD/packages/databox" --job gbif_ingest
```

Result:

```text
run_id=3e0d6baf-2094-4c09-9851-6141d3fa14f3
RUN_SUCCESS
```

Final local warehouse inspection:

```text
raw_gbif.occurrences rows=5
relations=[
  ('raw_gbif', '_dlt_loads', 'BASE TABLE'),
  ('raw_gbif', '_dlt_version', 'BASE TABLE'),
  ('raw_gbif', 'occurrences', 'BASE TABLE')
]
core columns present: _source_url, accepted_taxon_key, basis_of_record,
decimal_latitude, decimal_longitude, key, license, occurrence_status,
references, scientific_name
```

## What this supports

- `gbif` is registered as a Databox source and Dagster source domain.
- Local Quack-backed dlt ingestion can create physical `raw_gbif` base tables.
- GBIF raw records preserve identifiers, taxonomy/name fields, occurrence date/location fields, status fields, and provenance/license fields used by later planner modeling.
- dlt metadata relations created by the GBIF smoke load are raw-schema base tables; no persistent `main._dlt*` views/tables were observed.
- Source-layout and definition checks recognize GBIF as a first-class source.

### Final worker validation pass

A final validation pass also ran the complete repository CI command after the focused checks:

```bash
task ci
```

Result:

```text
ruff check: passed
ruff format --check: passed
mypy packages/: passed
pytest: 128 passed
scripts/check_secrets.py .: passed
scripts/generate_staging.py --check: passed
scripts/generate_platform_health.py --check: passed
```

The final local `gbif_ingest` smoke run observed by this worker also succeeded:

```text
run_id=a4a79cfd-0158-4244-95b1-a79850eab4f1
RUN_SUCCESS
raw_gbif.occurrences rows=5
raw_gbif._dlt_loads BASE TABLE
raw_gbif._dlt_version BASE TABLE
main _dlt relations=[]
```

A previous immediate rerun failed once with `data/.quack-clients/client-<pid>.duckdb: No such file or directory` after prior cleanup removed the client directory. Recreating `data/.quack-clients` before the next Dagster validation run resolved it; `task full-refresh`/`task verify` already manage that directory around their logged runs.

## Limits

- The first endpoint is GBIF public occurrence search for Aves in the configured geography (`country_code=US`, `state_province="Arizona"`, `taxon_key=212` mapped to GBIF `classKey=212`). GBIF username/password credentials were not used because this endpoint does not require them.
- Only a 5-row smoke ingestion was run locally to limit external API usage.
- No CDM/planner SQLMesh models were added in this ticket; downstream planner-ready SQL interfaces are owned by `.10x/tickets/2026-07-08-model-birding-planner-sql-interfaces.md`.
