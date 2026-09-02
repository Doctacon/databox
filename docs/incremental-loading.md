# Incremental Loading

Every dlt source in Databox writes a Polaris-managed Iceberg table in S3 using
a declared primary key and write disposition. Local DuckDB consumes those raw
tables through the attached Polaris catalog. This page documents, per resource:

- **write disposition** — how new rows land: `merge`, `replace`, or `append`
- **primary / merge key** — how dlt deduplicates on re-run
- **watermark** — how the extract window is bounded (date-based lookback, or none)
- **idempotency guarantee** — what re-running the same load against the same
  upstream data does to the final row set
- **backfill command** — exact command to reload a wider window

## Summary

| Source | Resource | Disposition | Primary Key | Watermark |
| --- | --- | --- | --- | --- |
| ebird | `recent_observations` | merge | `(subId, speciesCode)` | rolling `days_back` window |
| ebird | `notable_observations` | merge | `(subId, speciesCode)` | rolling `days_back` window |
| ebird | `species_list` | replace | `speciesCode` | none — full snapshot |
| ebird | `hotspots` | merge | `locId` | none — full snapshot |
| ebird | `taxonomy` | replace | `sciName` | none — full snapshot |
| ebird | `region_stats` | merge | `(regionCode, year, month, day)` | rolling `days_back` window |
| noaa | `daily_weather` | merge | `(date, datatype, station)` | rolling `days_back` window, chunked to 365-day API calls |
| noaa | `stations` | merge | `id` | none — full snapshot |
| noaa | `datasets` | replace | `id` | none — full snapshot |
| usgs | `daily_values` | merge | `(site_no, parameter_cd, observation_date)` | rolling `days_back` window, chunked to 90-day API calls |
| usgs | `sites` | merge | `site_no` | none — full snapshot |
| avonet | `species_traits` | Iceberg replace | `avibase_id` plus unique source scientific name | none — pinned full snapshot |

## Idempotency model

No resource uses dlt's `dlt.sources.incremental` cursor. Instead, every
resource re-fetches a bounded window on each run, and dlt commits declared
merge or replacement semantics through Iceberg. Consequences:

- **merge-disposition resources** are fully idempotent: re-running with the
  same API responses leaves the final table untouched.
- **replace-disposition resources** (`species_list`, `taxonomy`, `datasets`)
  drop and reload the table every run; idempotency is trivial because the
  row set is always "whatever the API returned this time."
- **AVONET complete snapshot** validates its pinned file identity, row count,
  unique identifiers/names, columns, provenance, and dlt metadata before direct
  replacement. The committed Iceberg snapshot is the atomic boundary; failed
  validation cannot publish, and a failed commit leaves the prior snapshot
  authoritative.

The merge-disposition guarantee is validated in CI by
`packages/databox-sources/tests/<source>/test_idempotency.py`: each test
runs the merge-backed resource twice against the same VCR cassette and
asserts the primary-key set and row count are identical. The Iceberg merge uses
the same declared primary keys for the current source set.

## Backfill procedure

All three sources read their extract window from a per-source env-var
override (default `30`) in
`packages/databox/databox/config/settings.py`:

- `DATABOX_EBIRD_DAYS_BACK`
- `DATABOX_NOAA_DAYS_BACK`
- `DATABOX_USGS_DAYS_BACK`

Set a supported window before launching the Dagster ingest job or
`task full-refresh`:

```bash
# Full-year NOAA backfill (hits multiple 365-day chunks; expect 5-10 min)
DATABOX_NOAA_DAYS_BACK=365 task full-refresh

# USGS daily values for the last year (chunked to 90-day API calls)
DATABOX_USGS_DAYS_BACK=365 task full-refresh
```

The eBird recent-observation endpoints accept only 1–30 days, so
`DATABOX_EBIRD_DAYS_BACK` is validated to that range and defaults to the maximum
30. Historical eBird backfill requires a different data product and is not wired
into this repository.

The merge disposition means a backfill never duplicates rows already present
at the narrower window — it only fills in older dates. If the API has
retroactively revised a row (which NOAA does for GHCND), the merge updates
in place.

### Blast radius

- **merge resources**: only the rows whose primary keys appear in the new
  window are touched. Existing rows outside the window are untouched.
- **replace resources**: the entire table is dropped and reloaded on every
  run, so a backfill on `days_back` has no effect on these (they always
  reflect the current full snapshot). AVONET reaches the same authoritative
  result through its separately validated Iceberg replacement.
- **downstream SQLMesh CDM models**: all are declarative views/tables over the
  raw layer. A backfill at the source layer is picked up on the next
  `task full-refresh` (or native SQLMesh restatement).

## Dagster backfill

A partitioned Dagster backfill is not wired yet, but each default registered
source has an independent dlt ingest asset job. `task full-refresh` validates
Polaris/S3 configuration, runs sources marked `parallel_refresh=True`
concurrently, verifies registry-declared Iceberg tables and explicit load
status, then uses the native SQLMesh CLI only after every source succeeds.
Static AVONET remains an explicit `avonet_ingest` bootstrap job with no daily
schedule; explicit-target USFWS has no unconfigured ingest job.

## When to rely on merge vs replace

- **merge**: the source API returns a durable, point-in-time row identified
  by a stable key (`(subId, speciesCode)`, `(date, datatype, station)`, `(site_no,
  parameter_cd, observation_date)`). Revisions are in-place updates.
- **replace**: the source API returns a catalog or reference list that
  should exactly mirror upstream (taxonomy, dataset manifest, species list
  for a region). Drift between a stale merge table and a current catalog
  would be worse than the cost of a full reload.
