# Source Layout Convention

Every registered dlt source in Databox follows the same ingestion shape.
SQLMesh CDM models are not per-source required files; they live under the CDM
schema after the `.schema` workflow is reviewed.

`scripts/check_source_layout.py` enforces this convention locally and in CI.

## The shape

For a source named `<name>`:

```text
packages/databox-sources/databox_sources/<name>/
  └── source.py              # dlt @source / @resource definitions

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

Skipped sources appear in lint output marked `~ (incomplete: <reason>)`. They
remain locally visible but fail the completed contract and registry-derived CI
matrix until every profile obligation passes. Do not use the marker to silence
drift in a finished source.

## Why each file is required

| Component | Why it is required |
|---|---|
| `source.py` | Anchor file — if this doesn't exist, the source isn't loadable. |
| `databox.config.sources.SOURCES` | Canonical identity, raw-table inventory, cadence flags, freshness, domain identity, and verification profile. |
| `domains/<name>.py` | Exactly one callable source builder, Dagster dlt assets/keys/checks, and independent ingest job; recurring sources also expose a daily job and schedule. |
| `tests/<name>/` | Profile-required resource, schema, smoke, idempotency, and (for file snapshots) staged-publication coverage. |

Static pinned sources set `scheduled=False`, `parallel_refresh=False`, and the
`file_snapshot` verification profile in the source registry. AVONET is the
current example: `avonet_ingest` is independently runnable, has no daily
schedule, and is intentionally absent from the shared full refresh. Its
source-specific `config.yaml` remains a pinned integrity manifest rather than
generic pipeline configuration. Every future `file_snapshot` source must add an
equivalent source-specific manifest plus `test_staged_publish.py`; the scaffold
does not invent integrity values. Its dlt load targets transient
`raw_avonet_staging`; final `raw_avonet` is published atomically only after the
independent Quack server stops.

## Adding model behavior

After a source lands and raw dlt schemas exist, use the project skills in order:

1. `annotate-sources`
2. `create-ontology`
3. `generate-cdm`
4. `create-transformation`

`create-transformation` writes SQLMesh CDM models; it does not create dlt
transformation scripts.
