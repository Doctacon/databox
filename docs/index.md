# Databox

Databox is a local-first ingestion and data-product platform with dlt-managed
Iceberg raw tables on AWS S3, a local Apache Polaris catalog, and DuckDB
transformations. SQLMesh transforms data, Soda validates it, and Dagster
orchestrates the workflow.

<a id="whats-here"></a>

## Start here

### Evaluate offline

```bash
task install   # creates .env from .env.example when absent
task ci
```

This runs the repository's static, test, secret, and generated-artifact gates.
It does not require a provider refresh or populated warehouse.

### Build and inspect the warehouse

Configure source, Polaris, and AWS S3 writer values in the `.env` created by
`task install`, then run:

```bash
$EDITOR .env
docker compose --env-file .env -f compose.iceberg.yml up -d
task full-refresh   # ingest Iceberg raw tables → local models → quality
task dagster:dev    # inspect assets at localhost:3000
```

Raw tables live in S3 and are registered by local Polaris; modeled data and
export inputs live in `data/databox.duckdb`. See
[configuration](configuration.md), the [commands reference](commands.md), and
the [operations runbook](runbook.md).

### Understand the data

- [Data dictionary](dictionary/index.md) — models, columns, types, contracts,
  and direct lineage
- [Lineage](dictionary/lineage.md) — the complete model dependency graph
- [Analytics examples](analytics-examples.md) — representative CDM queries
- [Metrics](metrics.md) — canonical semantic metrics
- [Contracts](contracts.md) — Soda quality conventions

### Add a source

Start with the [new-source workflow](new-source.md), then follow the authoritative
[source layout](source-layout.md). After ingestion, the project skills move each
source through annotation and taxonomy, ontology, Kimball CDM design, and SQLMesh
transformation. The registry-derived modeling guard verifies that every source
completes this chain.

<a id="architecture-decisions"></a>

## Operating and extending

- [Incremental loading](incremental-loading.md)
- [Environments](environments.md)
- [Freshness](freshness.md)
- [Observability](observability.md)
- [CI routing](ci.md)
- [Protected Polaris/S3 verification](ci.md#protected-live-integration) — manual real-provider integration gate
- [Rufous data-product boundary](https://github.com/Doctacon/databox/blob/main/.10x/specs/databox-rufous-data-product-boundary.md) — versioned consumer artifact contract
- [Architecture decisions](adr/README.md)

<a id="regenerate"></a>

Everything under [`dictionary/`](dictionary/index.md) is generated from SQLMesh
and Soda metadata. Do not hand-edit it.
