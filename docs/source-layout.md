# Source Layout Convention

Every registered dlt source in Databox follows the same ingestion shape.
SQLMesh CDM models are not per-source required files; they live under the CDM
schema after the `.schema` workflow is reviewed.

`scripts/check_source_layout.py` enforces this convention locally and in CI.

## The shape

For a source named `<name>`:

```text
packages/databox-sources/databox_sources/<name>/
  ├── source.py              # dlt @source / @resource definitions
  └── config.yaml            # pipeline config and source-specific options

packages/databox/databox/orchestration/domains/<name>.py
                             # Dagster dlt asset, ingest job, schedule
```

SQLMesh implementation happens later, after annotation/ontology/CDM review:

```text
.schema/<cdm-name>/...
transforms/main/models/<cdm-name>/
soda/contracts/<cdm-name>/
```

## Escape hatch: `scaffold-lint: skip`

Experimental or in-flight sources that don't yet satisfy the ingestion layout can
opt out by adding a line within the first 10 lines of `source.py`:

```python
# scaffold-lint: skip=experimental
```

Skipped sources appear in lint output marked `~ (skipped: <reason>)` but do not
fail CI. Do not use the marker to silence drift in a finished source.

## Why each file is required

| Component | Why it is required |
|---|---|
| `source.py` | Anchor file — if this doesn't exist, the source isn't loadable. |
| `config.yaml` | Pipeline configuration and source-specific options. |
| `domains/<name>.py` | Dagster wiring for dlt asset, ingest job, and schedule. |

## Adding model behavior

After a source lands and raw dlt schemas exist, use the project skills in order:

1. `annotate-sources`
2. `create-ontology`
3. `generate-cdm`
4. `create-transformation`

`create-transformation` writes SQLMesh CDM models; it does not create dlt
transformation scripts.
