Status: recorded
Created: 2026-07-07
Updated: 2026-07-07
Relates-To: .10x/tickets/done/2026-07-07-align-cdm-workflow-with-sqlmesh.md

# Evidence: CDM SQLMesh migration and legacy model retirement

## What was observed

The environmental observations CDM was generated, implemented as SQLMesh models, validated, promoted to prod, and the legacy source-specific SQLMesh staging/intermediate/mart layer was retired.

## Procedure and results

1. Generated `.schema/environmental_observations/CDM.dbml` from ontology artifacts.
2. Added SQLMesh CDM models under `transforms/main/models/environmental_observations/`.
3. Ran SQLMesh dev plan before legacy deletion:

   ```bash
   cd transforms/main && ../../.venv/bin/sqlmesh plan dev --auto-apply --no-prompts
   ```

   Result: passed after fixing one ambiguous `site_no` reference in `fact_streamflow_observation`.

4. Ran destination-native row/key/FK checks against `environmental_observations__dev`.

   Observed counts before full production refresh:

   ```text
   dim_species=17892
   dim_bird_hotspot=2913
   dim_weather_station=1721
   dim_streamgage_site=205
   fact_bird_observation=2404
   fact_region_daily_stats=31
   fact_weather_observation=28083
   fact_streamflow_observation=6236
   fact_earthquake_event=464
   pk duplicate checks=0
   FK missing checks=0
   ```

5. Removed superseded legacy SQLMesh models and model-specific Soda contracts:
   - source-specific `ebird`, `noaa`, `usgs`, `usgs_earthquakes` staging/intermediate/mart models
   - legacy analytics fact models
   - retained `analytics.platform_health`

6. Ran SQLMesh tests and prod promotion/restatement:

   ```bash
   cd transforms/main && ../../.venv/bin/sqlmesh test
   cd transforms/main && ../../.venv/bin/sqlmesh plan prod --auto-apply --no-prompts
   ```

   Result: `2` SQLMesh tests passed; prod virtual layer promoted.

7. Ran repository CI:

   ```bash
   task ci
   ```

   Result: passed — `119 passed`, ruff, format, mypy, secret scan, staging drift, and platform-health drift checks completed successfully.

8. Ran production full refresh:

   ```bash
   task full-refresh
   ```

   Result: passed, log at `.logs/full-refresh-20260707-202617.log`.

9. Ran final Dagster definitions check:

   ```bash
   .venv/bin/dg check defs --use-active-venv
   ```

   Result: `All definitions loaded successfully.` No Dagster supersession/preview warnings were observed.

10. Ran Soda contract verification helper:

    ```bash
    .venv/bin/python scripts/verify_dev.py
    ```

    Result: all active contracts passed, including CDM, platform health, and retained raw contracts.

11. Queried production CDM counts after `task full-refresh`:

    ```text
    dim_species=17892
    dim_bird_hotspot=2913
    dim_weather_station=1721
    dim_streamgage_site=205
    fact_bird_observation=2474
    fact_region_daily_stats=32
    fact_weather_observation=28083
    fact_streamflow_observation=6245
    fact_earthquake_event=516
    platform_health=4
    legacy=0
    ```

    `legacy=0` means no tables remained in retired source-specific SQLMesh schemas or legacy analytics fact tables:
    `ebird`, `ebird_staging`, `noaa`, `noaa_staging`, `usgs`, `usgs_staging`, `usgs_earthquakes`, `usgs_earthquakes_staging`, or `analytics.fct_*`.

## What this supports

- SQLMesh remains the transformation layer.
- dlt remains ingestion-only.
- The `.schema` CDM workflow now drives SQLMesh model implementation.
- Superseded legacy SQLMesh marts were retired only after CDM model validation.
- Dagster definitions, SQLMesh tests, Soda contracts, and CI are coherent after cleanup.

## Limits

- Full refresh validated the local Quack/DuckDB path. MotherDuck was not exercised in this evidence run.
- CDM contracts cover structural/key/row-count checks; deeper semantic assertions can be added as the CDM evolves.
