# Adding a New Source

The goal is simple: **clone the scaffold, run one command, fill in the TODOs.** From "I want to ingest X" to "I have a running empty pipeline" should be under 60 seconds.

## The generator

```bash
task new-source -- mysource --shape rest
```

Shapes:

- `rest` — REST/GraphQL API with a bearer-token env var (default)
- `file` — filesystem or object-store source (local path, S3, GCS)
- `database` — SQL database connector with a DSN env var

The generator:

1. Creates the full layout required by [`docs/source-layout.md`](source-layout.md):
   - `packages/databox-sources/databox_sources/mysource/{__init__.py,source.py,config.yaml}`
   - `transforms/main/models/mysource/{staging,marts}/.gitkeep`
   - `soda/contracts/{mysource_staging,mysource}/.gitkeep`
   - `packages/databox/databox/orchestration/domains/mysource.py`
2. Adds `mysource` to the imports in `packages/databox/databox/orchestration/definitions.py` and splats its (empty) asset/check lists into the relevant collections.
3. For `--shape rest`, appends `API_KEY_MYSOURCE=` to `.env.example` if missing.
4. Prints a 5-step next-steps list.

The generated `source.py` carries a `# scaffold-lint: skip=scaffolded` marker on line 1. That marker tells `scripts/check_source_layout.py` to tolerate the missing staging/mart/contract files while you build out the source — the layout lint still runs, but the scaffold row shows `~ mysource (skipped: scaffolded)` instead of failing.

## Flags

| Flag | Meaning |
| --- | --- |
| `--shape {rest,file,database}` | Which template set to use (default `rest`) |
| `--dry-run` | Print the planned file tree, write nothing |
| `--force` | Overwrite files that already exist on disk (by default the generator refuses on collision) |

## Naming rules

Source names must match `^[a-z][a-z0-9_]*$`. Reserved names (`analytics`, `_shared`, `base`, `registry`) are rejected.

Pick a short slug — it shows up in table names, dataset names, file paths, and CLI output. `noaa_cdo` is fine; `national_oceanic_and_atmospheric_administration_climate_data_online` is not.

## First-flight walkthrough

```bash
# 1. Scaffold.
task new-source -- weather --shape rest

# 2. Verify the layout lint is happy with the scaffolded-skip marker.
python scripts/check_source_layout.py
# Expect:
#   ~ weather (skipped: scaffolded)

# 3. Fill in source.py — define at least one @dlt.resource, update base URL,
#    implement pagination. See packages/databox-sources/databox_sources/usgs/source.py
#    for a canonical example.

# 4. Remove the `# scaffold-lint: skip=scaffolded` marker from source.py.
#    From here, the layout lint starts checking for staging/mart/contract files.

# 5. Add at least one staging SQL file under transforms/main/models/weather/staging/
#    (name it `stg_weather_*.sql`). If your source is a "trivial rename" of raw
#    columns, you can let the staging codegen write it — add a Soda contract under
#    soda/contracts/weather_staging/ with the full column list, then run:
python scripts/generate_staging.py

# 6. Add at least one mart under transforms/main/models/weather/marts/
#    (`fct_*.sql` or `dim_*.sql`). This is your consumer-facing table.

# 7. Add a Soda contract for the mart under soda/contracts/weather/.

# 8. Wire the real Dagster assets in domains/weather.py — see usgs.py as the
#    canonical reference for shape. Then uncomment and fill in the empty
#    splat wiring in definitions.py.

# 9. Full run.
task full-refresh

# 10. Regenerate the data dictionary so the site picks up the new models.
#     CI enforces this via `generate_docs.py --check`; skipping it means
#     your PR will fail the `docs-drift-check` gate.
uv run python scripts/generate_docs.py
```

## What the empty domain stub looks like

```python
# packages/databox/databox/orchestration/domains/weather.py
from __future__ import annotations

import dagster as dg

dlt_asset_keys: list[dg.AssetKey] = []
sqlmesh_asset_keys: list[dg.AssetKey] = []
asset_checks: list[dg.AssetChecksDefinition] = []
```

The three list names are the contract that `definitions.py` wires into its splat lists. As you build out the domain, populate each list — don't rename them.

## Idempotency and collisions

Running `task new-source -- weather` twice without `--force` refuses to overwrite. Running with `--force` regenerates every file from the template. Wiring in `definitions.py` is always idempotent — it won't duplicate entries.

For `--dry-run`, the generator prints what it would write (marking any pre-existing paths) and exits without touching the filesystem.

## Extending the generator

Templates live under `scripts/templates/source/`:

```
scripts/templates/source/
├── common/
│   ├── __init__.py.j2
│   └── domain.py.j2
├── rest/
│   ├── source.py.j2
│   └── config.yaml.j2
├── file/ …
└── database/ …
```

To add a new shape (e.g. `streaming`), create `scripts/templates/source/streaming/{source.py.j2,config.yaml.j2}` and add `"streaming"` to `SHAPES` in `scripts/new_source.py`. Templates receive these Jinja context vars: `name`, `name_upper`, `name_title`.

## Related

- [`docs/source-layout.md`](source-layout.md) — the layout convention the generator produces
- [`docs/staging.md`](staging.md) — staging-model codegen from Soda contracts
- [`docs/template.md`](template.md) — one-command fork rebrand (separate from per-source scaffolding)
