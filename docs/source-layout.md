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
                             # Dagster dlt asset and independent ingest job;
                             # recurring sources also expose a schedule
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
| `domains/<name>.py` | Dagster wiring for a dlt asset and independent ingest job; recurring sources also expose a schedule. |

Static pinned sources set `scheduled=False` and `parallel_refresh=False` in the
source registry when they must remain explicit bootstrap jobs. AVONET is the
current example: `avonet_ingest` is independently runnable, has no daily
schedule, and is intentionally absent from the shared full refresh. Its dlt
load targets transient `raw_avonet_staging`; final `raw_avonet` is published
atomically only after the independent Quack server stops.

## Adding model behavior

After a source lands and raw dlt schemas exist, use the project skills in order:

1. `annotate-sources`
2. `create-ontology`
3. `generate-cdm`
4. `create-transformation`

`create-transformation` writes SQLMesh CDM models; it does not create dlt
transformation scripts.
