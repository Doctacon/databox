# Adding a New Source

The generator creates a dlt ingestion scaffold. CDM modeling happens after raw
schemas exist and have gone through the `.schema` workflow.

## The generator

```bash
task new-source -- mysource --shape rest
```

Shapes:

- `rest` — REST/GraphQL API with a bearer-token env var (default)
- `file` — filesystem or object-store source (local path, S3, GCS)
- `database` — SQL database connector with a DSN env var

The generator:

1. Creates the ingestion layout required by [`docs/source-layout.md`](source-layout.md):
   - `packages/databox-sources/databox_sources/mysource/{__init__.py,source.py,config.yaml}`
   - `packages/databox/databox/orchestration/domains/mysource.py`
2. Adds `mysource` to `packages/databox/databox/orchestration/definitions.py`.
3. Adds `mysource` to `packages/databox/databox/config/sources.py` with an empty
   `raw_tables` tuple for the operator to fill once resources are real.
4. For `--shape rest`, appends `API_KEY_MYSOURCE=` to `.env.example` if missing.
5. Prints next steps.

The generated `source.py` carries a `# scaffold-lint: skip=scaffolded` marker on
line 1. Remove it once `source.py`, `config.yaml`, and the Dagster domain module
are real.

## First-flight walkthrough

```bash
# 1. Scaffold.
task new-source -- weather --shape rest

# 2. Fill in source.py — define at least one @dlt.resource, update base URL,
#    implement pagination. See packages/databox-sources/databox_sources/usgs/source.py
#    for a canonical example.

# 3. Fill raw_tables for the Source(name="weather", ...) entry once the dlt
#    resources are known.

# 4. Remove the scaffold-lint marker and verify ingestion layout.
python scripts/check_source_layout.py

# 5. Run the source once so local dlt schema JSON exists under data/dlt/.
task verify

# 6. Extend the CDM workflow:
#    annotate-sources → create-ontology → generate-cdm → create-transformation.
#    create-transformation writes SQLMesh models, not dlt transformation scripts.

# 7. Regenerate docs after SQLMesh models/contracts change.
uv run python scripts/generate_docs.py
```

## Flags

| Flag | Meaning |
|---|---|
| `--shape {rest,file,database}` | Which template set to use (default `rest`) |
| `--dry-run` | Print the planned file tree, write nothing |
| `--force` | Overwrite files that already exist on disk |
| `--no-auth` | REST shape only: generate a public-endpoint stub and skip `.env.example` |

## Domain stub contract

The generated domain module exposes these names so `definitions.py` can compose
sources uniformly:

```python
dlt_asset_keys: list[dg.AssetKey] = []
sqlmesh_asset_keys: list[dg.AssetKey] = []
asset_checks: list[dg.AssetChecksDefinition] = []
```

For source domains, `sqlmesh_asset_keys` normally stays empty. Cross-source CDM
SQLMesh assets are wired from the analytics/CDM domain after the CDM changes.

## Related

- [`docs/source-layout.md`](source-layout.md) — ingestion layout convention
- [`docs/staging.md`](staging.md) — optional legacy staging codegen guardrail
- [`docs/template.md`](template.md) — one-command fork rebrand
