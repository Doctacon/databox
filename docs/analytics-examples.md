# Analytics Examples

Example queries against the flagship cross-domain mart, `analytics.fct_species_environment_daily`.

## The Mart

`analytics.fct_species_environment_daily` joins three sources at **species × H3 cell (resolution 6, ~36 km² hex) × day** grain:

| Source | Values |
|--------|--------|
| eBird | `n_observations`, `n_checklists`, `total_birds_counted`, `n_notable_observations` |
| NOAA | `tmax_c`, `tmin_c`, `temp_range_c`, `prcp_mm`, `snow_mm`, `wind_ms`, `is_rainy_day`, `nearest_station_id`, `nearest_station_distance_miles` |
| USGS | `mean_discharge_cfs`, `mean_gage_height_ft`, `mean_water_temp_c`, `nearest_gauge_id`, `nearest_gauge_distance_miles` |

The grain is unique on `(species_code, h3_cell, obs_date)`. Weather and streamflow are LEFT-joined — when the nearest station/gauge has no observation for a given date, the environmental columns are NULL. (NOAA GHCND data has a multi-day publish lag, so recent dates frequently have NULL weather.)

## Example 1 — Species on Cold, Rainy Days

Which species show up in cold (tmax < 15 °C), rainy cells?

```sql
SELECT
    common_name,
    SUM(n_observations) AS obs,
    ROUND(AVG(prcp_mm)::NUMERIC, 2) AS avg_prcp_mm,
    ROUND(AVG(tmax_c)::NUMERIC, 1) AS avg_tmax_c
FROM databox.analytics.fct_species_environment_daily
WHERE is_rainy_day
  AND tmax_c < 15
GROUP BY common_name
ORDER BY obs DESC
LIMIT 20;
```

## Example 2 — Species Diversity by H3 Cell

Which cells have the highest species diversity, and what does the weather look like there?

```sql
SELECT
    h3_cell,
    ROUND(AVG(cell_center_lat)::NUMERIC, 3) AS lat,
    ROUND(AVG(cell_center_lng)::NUMERIC, 3) AS lng,
    COUNT(DISTINCT species_code) AS species_count,
    SUM(n_observations) AS obs,
    ROUND(AVG(tmax_c)::NUMERIC, 1) AS avg_tmax_c,
    ROUND(AVG(prcp_mm)::NUMERIC, 2) AS avg_prcp_mm
FROM databox.analytics.fct_species_environment_daily
GROUP BY h3_cell
ORDER BY species_count DESC
LIMIT 10;
```

## Example 3 — Bird Activity vs. Streamflow Regime

Do bird counts cluster at low-flow, medium-flow, or high-flow gauges?

```sql
SELECT
    CASE
        WHEN mean_discharge_cfs < 100 THEN 'low'
        WHEN mean_discharge_cfs < 1000 THEN 'medium'
        ELSE 'high'
    END AS flow_bucket,
    COUNT(DISTINCT species_code) AS species,
    SUM(n_observations) AS obs,
    ROUND(AVG(mean_discharge_cfs)::NUMERIC, 1) AS avg_cfs
FROM databox.analytics.fct_species_environment_daily
WHERE mean_discharge_cfs IS NOT NULL
GROUP BY 1
ORDER BY 1;
```

## Example 4 — Cold-Snap-After-Rainfall Species

Species seen the day after a rainy day where tmax dropped ≥ 5 °C compared to the previous day:

```sql
WITH daily AS (
    SELECT
        species_code,
        common_name,
        h3_cell,
        obs_date,
        tmax_c,
        prcp_mm,
        n_observations,
        LAG(tmax_c) OVER (PARTITION BY h3_cell ORDER BY obs_date) AS prev_tmax_c,
        LAG(prcp_mm) OVER (PARTITION BY h3_cell ORDER BY obs_date) AS prev_prcp_mm
    FROM databox.analytics.fct_species_environment_daily
)
SELECT
    common_name,
    COUNT(DISTINCT obs_date) AS days_seen,
    SUM(n_observations) AS obs
FROM daily
WHERE prev_prcp_mm > 5.0
  AND prev_tmax_c - tmax_c >= 5.0
GROUP BY common_name
ORDER BY obs DESC
LIMIT 10;
```

## Running the Queries

### MotherDuck

```bash
uv run python -c "
import os, duckdb
con = duckdb.connect(f'md:databox?motherduck_token={os.environ[\"MOTHERDUCK_TOKEN\"]}')
print(con.execute('SELECT COUNT(*) FROM analytics.fct_species_environment_daily').fetchone())
"
```

### Local DuckDB

```bash
uv run python -c "
import duckdb
con = duckdb.connect('data/databox.duckdb')
print(con.execute('SELECT COUNT(*) FROM analytics.fct_species_environment_daily').fetchone())
"
```

Or point the Streamlit explorer at the same database:

```bash
uv run streamlit run app/main.py
```
