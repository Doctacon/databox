# Source Layout Convention

Every registered dlt source in Databox follows the same ingestion shape.
SQLMesh CDM models are not per-source required files; they live under the CDM
schema after the `.schema` workflow is reviewed.

`scripts/sources/check_source_layout.py` enforces this convention locally and in CI.

## The shape

For a source named `<name>`:

```text
packages/databox-sources/databox_sources/<name>/
  └── source.py              # dlt @source / @resource definitions

packages/databox/databox/orchestration/domains/<name>.py
                             # Source builder and registry-governed Dagster exports;
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
| `databox.config.sources.SOURCES` | Canonical identity, raw-table inventory, cadence flags, freshness, domain identity, verification profile, and orchestration mode. |
| `domains/<name>.py` | Exactly one callable source builder and exports matching the orchestration mode. Default sources expose Dagster dlt assets/keys/checks and an independent ingest job; recurring sources also expose a daily job and schedule. Explicit-target sources may expose a manual job only when targets come fail-closed from an explicit modeled dependency. |
| `tests/<name>/` | Profile-required resource, schema, smoke, idempotency, and (for file snapshots) fail-closed replacement coverage. |

Static pinned sources set `scheduled=False`, `parallel_refresh=False`, and the
`file_snapshot` verification profile in the source registry. AVONET is the
current example: `avonet_ingest` is independently runnable, has no daily
schedule, and is intentionally absent from the shared full refresh. Its
source-specific `config.yaml` remains a pinned integrity manifest rather than
generic pipeline configuration. Every future `file_snapshot` source must add an
equivalent source-specific manifest plus fail-closed replacement coverage; the
scaffold does not invent integrity values. AVONET publishes the validated full
snapshot directly through dlt as a Polaris-managed Iceberg replacement; the
committed Iceberg snapshot is the atomic publication boundary.

Sources with `orchestration_mode="explicit_targets"` have no safe unconfigured
input snapshot. They must remain unscheduled and absent from shared parallel
refresh. Their domain module retains a callable builder and may expose a
manually launched Dagster job only when the target set is derived fail-closed
from an explicit modeled dependency. USFWS is the current example:
`usfws_ingest` reads the configured local `rufous_public.gbif_eod_occurrence`
relation, validates the complete target snapshot before provider contact, and
materializes its Polaris Iceberg records and load status. Do not embed or
invent an implicit species target set.

## Adding model behavior

After a source lands and raw dlt schemas exist, use the project skills in order:

1. `annotate-sources`
2. `create-ontology`
3. `generate-cdm`
4. `create-transformation`

`create-transformation` writes SQLMesh CDM models; it does not create dlt
transformation scripts.

`scripts/sources/check_source_modeling.py` and
`tests/sources/test_source_modeling_contract.py` enforce this chain for every registry
source. Every registered raw table must be modeled or explicitly excluded with
a reason; modeled concepts must reach the ontology and CDM; modeled tables must
have AST-parsed SQLMesh `FROM`/`JOIN` dependencies in CDM-declared models with
matching source entities (write targets do not count); and every source must
contribute at least one transformed business table. Changes under `.schema/` or SQLMesh
models trigger the full CI suite.
