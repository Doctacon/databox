# Databox

Dataset-agnostic single-operator data platform. Ingests bird, weather, and
streamflow sources with dlt, transforms with SQLMesh, validates with Soda
contracts, and orchestrates with Dagster on DuckDB / MotherDuck.

## What's here

- **[Data dictionary](dictionary/index.md)** — every model, its columns and
  types, the Soda contract in effect, and direct lineage. Auto-generated
  from SQLMesh and Soda metadata.
- **[Lineage](dictionary/lineage.md)** — full model dependency graph rendered
  with Mermaid. Each node links to its dictionary page.
- **[Metrics](metrics.md)** — semantic metrics layer over the flagship mart
  (`analytics.fct_species_environment_daily`).
- **[Analytics examples](analytics-examples.md)** — representative queries
  the flagship mart supports.
- **[Contracts](contracts.md)** — Soda quality contract conventions.
- **[Incremental loading](incremental-loading.md)** — dlt incremental and
  SQLMesh incremental-by-time notes.

## Architecture decisions

Six backfilled ADRs (Nygard format) explain the load-bearing choices:

- [ADR-0001 — DuckDB as the primary warehouse](adr/0001-duckdb-as-primary-warehouse.md)
- [ADR-0002 — SQLMesh over dbt](adr/0002-sqlmesh-over-dbt.md)
- [ADR-0003 — Single SQLMesh project across all sources](adr/0003-single-sqlmesh-project.md)
- [ADR-0004 — Per-source raw DuckDB catalogs](adr/0004-per-source-raw-catalogs.md)
- [ADR-0005 — Dagster as the sole orchestrator](adr/0005-dagster-as-sole-orchestrator.md)
- [ADR-0006 — MotherDuck as the cloud path](adr/0006-motherduck-as-cloud-path.md)

The root README frames the platform as a case study with system and
data-flow diagrams in Mermaid.

## Regenerate

Everything under [dictionary/](dictionary/index.md) is generated from the repo — do
not hand-edit. Rebuild with:

```bash
uv run python scripts/generate_docs.py
```

Target runtime: under 30 seconds; observed runtime: ~1–2 seconds for the
current model set.
