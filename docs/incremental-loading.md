# Incremental Loading

Every dlt source in Databox writes to DuckDB (local or MotherDuck) using a
declared primary key and write disposition. This page documents, per resource:

- **write disposition** — how new rows land: `merge`, `replace`, or `append`
- **primary / merge key** — how dlt deduplicates on re-run
- **watermark** — how the extract window is bounded (date-based lookback, or none)
- **idempotency guarantee** — what re-running the same load against the same
  upstream data does to the final row set
- **backfill command** — exact command to reload a wider window

## Summary

| Source | Resource | Disposition | Primary Key | Watermark |
| --- | --- | --- | --- | --- |
| ebird | `recent_observations` | merge | `subId` | rolling `days_back` window |
| ebird | `notable_observations` | merge | `subId` | rolling `days_back` window |
| ebird | `species_list` | replace | `speciesCode` | none — full snapshot |
| ebird | `hotspots` | merge | `locId` | none — full snapshot |
| ebird | `taxonomy` | replace | `sciName` | none — full snapshot |
| ebird | `region_stats` | merge | `(regionCode, year, month, day)` | rolling `days_back` window |
| noaa | `daily_weather` | merge | `(date, datatype, station)` | rolling `days_back` window, chunked to 365-day API calls |
| noaa | `stations` | merge | `id` | none — full snapshot |
| noaa | `datasets` | replace | `id` | none — full snapshot |
| usgs | `daily_values` | merge | `(site_no, parameter_cd, observation_date)` | rolling `days_back` window, chunked to 90-day API calls |
| usgs | `sites` | merge | `site_no` | none — full snapshot |

## Idempotency model

No resource uses dlt's `dlt.sources.incremental` cursor. Instead, every
resource re-fetches a bounded window on each run and relies on the merge
primary key to deduplicate. Consequences:

- **merge-disposition resources** are fully idempotent: re-running with the
  same API responses leaves the final table untouched.
- **replace-disposition resources** (`species_list`, `taxonomy`, `datasets`)
  drop and reload the table every run; idempotency is trivial because the
  row set is always "whatever the API returned this time."
- No resource uses `append` — we accept the rate-limit cost of re-fetching
  over the complexity of durable cursor state.

The idempotency guarantee is validated in CI by
`packages/databox-sources/tests/<source>/test_idempotency.py`: each test
runs the merge-backed resource twice against the same VCR cassette and
asserts the primary-key set and row count are identical.

## Backfill procedure

All three sources read their extract window from a per-source env-var
override (default `30`) in
`packages/databox/databox/orchestration/definitions.py`:

- `DATABOX_EBIRD_DAYS_BACK`
- `DATABOX_NOAA_DAYS_BACK`
- `DATABOX_USGS_DAYS_BACK`

To widen the window for one run, set the env var before launching Dagster
and materialize the raw asset group:

```bash
# Pull eBird data for the last 90 days instead of the default 30
DATABOX_EBIRD_DAYS_BACK=90 uv run dagster asset materialize \
    --select 'group:ebird_ingestion' \
    -m databox.orchestration.definitions

# Full-year NOAA backfill (hits multiple 365-day chunks; expect 5-10 min)
DATABOX_NOAA_DAYS_BACK=365 uv run dagster asset materialize \
    --select 'group:noaa_ingestion' \
    -m databox.orchestration.definitions

# USGS daily values for the last year (chunked to 90-day API calls)
DATABOX_USGS_DAYS_BACK=365 uv run dagster asset materialize \
    --select 'group:usgs_ingestion' \
    -m databox.orchestration.definitions
```

Or launch the Dagster UI with the env var set and materialize the group
interactively — the UI-driven path is what the operator uses day-to-day.

The merge disposition means a backfill never duplicates rows already present
at the narrower window — it only fills in older dates. If the API has
retroactively revised a row (which NOAA does for GHCND), the merge updates
in place.

### Blast radius

- **merge resources**: only the rows whose primary keys appear in the new
  window are touched. Existing rows outside the window are untouched.
- **replace resources**: the entire table is dropped and reloaded on every
  run, so a backfill on `days_back` has no effect on these (they always
  reflect the current full snapshot).
- **downstream SQLMesh marts**: all are declarative views/tables over the raw
  layer. A backfill at the source layer is picked up on the next
  `task full-refresh` (or the next scheduled Dagster run).

## Dagster backfill

A per-source Dagster partition backfill is not wired yet — the current
orchestration layer schedules one daily materialization per source.
For ad-hoc historical loads, invoke `dagster asset materialize` directly
(see commands above) or materialize the raw asset via the Dagster UI with
a custom `days_back` config override.

See `packages/databox/databox/orchestration/definitions.py`
for the asset definitions that would host a future partition scheme.

## When to rely on merge vs replace

- **merge**: the source API returns a durable, point-in-time row identified
  by a stable key (`subId`, `(date, datatype, station)`, `(site_no,
  parameter_cd, observation_date)`). Revisions are in-place updates.
- **replace**: the source API returns a catalog or reference list that
  should exactly mirror upstream (taxonomy, dataset manifest, species list
  for a region). Drift between a stale merge table and a current catalog
  would be worse than the cost of a full reload.
