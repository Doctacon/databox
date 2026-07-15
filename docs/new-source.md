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

The generator:

1. Creates the ingestion layout required by [`docs/source-layout.md`](source-layout.md):
   - `packages/databox-sources/databox_sources/mysource/{__init__.py,source.py}`
   - `packages/databox/databox/orchestration/domains/mysource.py`
2. Adds `mysource` to `packages/databox/databox/config/sources.py` with an empty
   `raw_tables` tuple and the shape's verification profile for the operator to complete.
3. For `--shape rest`, appends `API_KEY_MYSOURCE=` to `.env.example` if missing.
4. Prints next steps. Dagster Definitions and CI derive completed sources from the registry.

The generated `source.py` carries a `# scaffold-lint: skip=scaffolded` marker on
line 1. The checker reports it as incomplete and exits nonzero, so it cannot
enter the CI matrix. Remove it only once `source.py`, its registry inventory,
required domain exports, and every profile test pass. A `file` scaffold must
also add a source-specific pinned `config.yaml` manifest and staged-publication
test; the generator cannot invent integrity values.

## First-flight walkthrough

```bash
# 1. Scaffold.
task new-source -- weather --shape rest

# 2. Fill in source.py — define at least one @dlt.resource, update base URL,
#    implement pagination. See packages/databox-sources/databox_sources/usgs/source.py
#    for a canonical example.

# 3. Fill raw_tables for the Source(name="weather", ...) entry once the dlt
#    resources are known.

# 4. Add the profile tests (and a pinned config.yaml + staged-publication test
#    for file_snapshot), then remove the scaffold-lint marker only when this passes.
python scripts/check_source_layout.py

# 5. Run the source explicitly through its bounded source job when authorized so
#    local dlt schema JSON exists under data/dlt/.

# 6. Extend the CDM workflow:
#    annotate-sources → create-ontology → generate-cdm → create-transformation.
#    create-transformation writes SQLMesh models, not dlt transformation scripts.

# 7. Regenerate docs after SQLMesh models/contracts change.
uv run python scripts/generate_docs.py
```

## Flags

| Flag | Meaning |
|---|---|
| `--shape {rest,file}` | Which approved verification profile to scaffold (default `rest`) |
| `--dry-run` | Print the planned file tree, write nothing |
| `--force` | Overwrite files that already exist on disk |
| `--no-auth` | REST shape only: generate a public-endpoint stub and skip `.env.example` |

## Domain stub contract

The generated domain module exposes these names so `definitions.py` can compose
sources uniformly:

```python
def _build_source(): ...

assets: list[dg.AssetsDefinition] = []
dlt_asset_keys: list[dg.AssetKey] = []
sqlmesh_asset_keys: list[dg.AssetKey] = []
asset_checks: list[dg.AssetChecksDefinition] = []
ingest_job = dg.define_asset_job(...)
# Scheduled registry entries also expose daily_pipeline and schedule.
```

These empty scaffold exports keep Dagster importable; they do not make the
source contract-valid. The completed domain must replace them with its real dlt
asset and must use the one builder for definition-time and execution-time source
construction.

For source domains, `sqlmesh_asset_keys` normally stays empty. Cross-source CDM
SQLMesh assets are wired from the analytics/CDM domain after the CDM changes.

## Related

- [`docs/source-layout.md`](source-layout.md) — ingestion layout convention
- [`docs/staging.md`](staging.md) — optional legacy staging codegen guardrail
- [`docs/template.md`](template.md) — one-command fork rebrand
