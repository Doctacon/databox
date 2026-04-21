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

## Case study

The case-study README (architecture walkthrough and decision record index) is
tracked in `ticket:architecture-docs` and will be linked from here once
published.

## Regenerate

Everything under [dictionary/](dictionary/index.md) is generated from the repo — do
not hand-edit. Rebuild with:

```bash
uv run python scripts/generate_docs.py
```

Target runtime: under 30 seconds; observed runtime: ~1–2 seconds for the
current model set.
