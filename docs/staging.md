# Staging Codegen

Trivial-rename staging models (`transforms/main/models/*/staging/stg_*.sql`) are generated from their Soda contracts rather than hand-written. The codegen exists because the staging layer is dominated by `SELECT old_col AS new_col` from a raw catalog — writing each one by hand scales poorly as sources grow.

Non-trivial staging (joins, UNION ALL, derived columns, filters) opts out with a skip marker and stays hand-maintained.

## How it runs

- `task staging:generate` — regenerate every non-skipped staging SQL in place.
- `task staging:check` — exit `1` if any committed staging SQL differs from what the generator would emit. Run in CI as the `staging-codegen-drift` job.

The generator lives in `databox.quality.staging_codegen`; `scripts/generate_staging.py` is a thin CLI wrapper.

## Contract extension

A codegen-driven staging contract adds two keys on top of the standard Soda layout:

```yaml
dataset: databox/ebird_staging/stg_ebird_hotspots
source_table: raw_ebird.main.hotspots
description: Staging model for eBird birding hotspots

columns:
  - name: location_id
    source_column: loc_id        # optional; defaults to `name` when omitted
    checks:
      - missing:
          must_be: 0
  - name: latitude
    source_column: lat
    data_type: DOUBLE            # optional; emits `lat::DOUBLE AS latitude` when present
  - name: country_code           # identity — no rename, no cast
```

Rules applied by the template:

| contract fields | emitted SQL |
| --- | --- |
| `name: x` | `x` |
| `name: x`, `source_column: y` | `y AS x` |
| `name: x`, `data_type: T` | `x::T AS x` |
| `name: x`, `source_column: y`, `data_type: T` | `y::T AS x` |

`description` becomes the model's `description '...'`. Columns are emitted in the order they appear in the contract. The grant list is hardcoded to `staging_reader`; if a staging model needs a different grant, use the escape hatch.

## Escape hatch

Add a `-- staging-codegen: skip` header on the first three lines of the target SQL and the generator will leave that file alone. Use it when the staging model needs behavior the template cannot express — UNION ALL, CASE, EXTRACT, joins, filters.

Example: `transforms/main/models/ebird/staging/stg_ebird_observations.sql` uses the skip marker because it UNIONs `recent_observations` and `notable_observations` and derives `observation_year/month/day/hour` columns.

When a skipped model's contract also omits `source_table`, that is fine — the generator checks for the skip marker before requiring the key.

## When to use which

| fits codegen | needs escape hatch |
| --- | --- |
| pure column renames | joins across raw tables |
| cast-only transforms | UNION ALL |
| identity passthrough | CASE / EXTRACT / other derivations |
|  | row filtering |

The default should be codegen. Reach for the escape hatch only when the template genuinely cannot express the staging shape.
