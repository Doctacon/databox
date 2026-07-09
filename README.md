# Databox

[![CI](https://github.com/Doctacon/databox/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/Doctacon/databox/actions/workflows/ci.yaml)
[![Docs](https://github.com/Doctacon/databox/actions/workflows/docs.yaml/badge.svg?branch=main)](https://doctacon.github.io/databox/)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](pyproject.toml)
[![coverage: ≥70%](https://img.shields.io/badge/coverage-%E2%89%A570%25-brightgreen.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A single-operator data platform that ingests public APIs (eBird,
NOAA, USGS) into one queryable cross-domain warehouse. Zero always-on
infra: Quack-backed local DuckDB. Every layer — ingest, transform,
quality, orchestration, semantic
metrics, data dictionary — is wired end-to-end through the same
open-source stack.

The project exists to answer one question: *"do species distributions
shift with same-day weather and streamflow anomalies?"* The platform
around it exists to answer that question honestly, repeatably, and
with receipts.

## Evaluate this repo in ten minutes

1. Skim the **System architecture** diagram below.
2. Skim the **Data flow** diagram below.
3. Open the **[data dictionary](https://doctacon.github.io/databox/)** —
   every model, columns, types, Soda checks, lineage.
4. Read **[ADR-0001 through ADR-0006](docs/adr/)** for the six load-bearing
   architectural decisions.
5. Read **[docs/analytics-examples.md](docs/analytics-examples.md)** to see
   what the cross-domain mart actually answers.

## System architecture

```mermaid
graph TB
    subgraph External["External APIs"]
        ebird_api[eBird API v2]
        noaa_api[NOAA CDO v2]
        usgs_api[USGS NWIS]
    end

    subgraph Ingest["Ingestion · dlt"]
        ebird_src[ebird source]
        noaa_src[noaa source]
        usgs_src[usgs source]
    end

    subgraph Raw["Raw schemas · DuckDB"]
        raw_ebird[(raw_ebird)]
        raw_noaa[(raw_noaa)]
        raw_usgs[(raw_usgs)]
    end

    subgraph Transform["Transform · SQLMesh"]
        cdm["environmental_observations CDM"]
        health["analytics.platform_health"]
        metrics["semantic metrics METRIC()"]
    end

    subgraph Quality["Quality · Soda Core"]
        contracts["Soda contracts per model"]
    end

    subgraph Consumer["Consumers"]
        dashboard["Local product"]
        dict["Data dictionary site (MkDocs)"]
    end

    Orchestrator["Dagster: sole orchestrator<br/>assets · schedules · sensors · asset checks"]

    ebird_api --> ebird_src --> raw_ebird
    noaa_api --> noaa_src --> raw_noaa
    usgs_api --> usgs_src --> raw_usgs
    raw_ebird --> cdm
    raw_noaa --> cdm
    raw_usgs --> cdm
    cdm --> metrics
    cdm --> contracts
    cdm --> dashboard
    cdm --> dict
    raw_ebird --> health
    raw_noaa --> health
    raw_usgs --> health
    health --> contracts

    Orchestrator -.materializes.-> ebird_src
    Orchestrator -.materializes.-> noaa_src
    Orchestrator -.materializes.-> usgs_src
    Orchestrator -.materializes.-> cdm
    Orchestrator -.materializes.-> health
    Orchestrator -.asset-checks.-> contracts
```

## Data flow

```mermaid
flowchart LR
    A[API responses<br/>JSON] -->|dlt incremental| B[raw_*<br/>append-only tables]
    B -->|.schema workflow| C[CDM contract<br/>CDM.dbml]
    C -->|SQLMesh models| D[environmental_observations<br/>dimensions + facts]
    D -->|METRIC DDL| G[semantic metrics<br/>richness · counts]
    D -->|Soda asset check| H{quality gate}
    H -->|pass| I[Local product]
    H -->|fail| J[block downstream · surface in Dagster]
```

## What this demonstrates

Each claim is backed by a ticket and its evidence, not just prose.

| Capability | How it shows up | Evidence |
|---|---|---|
| **Canonical data modeling** — raw source schemas become a reviewed CDM before SQL implementation | `.schema/environmental_observations/CDM.dbml` drives SQLMesh models under `environmental_observations.*` | [example queries](docs/analytics-examples.md) |
| **Semantic metrics layer** — one canonical SQL definition per KPI | CDM metrics in `transforms/main/metrics/flagship.sql`, queryable by name via `resolve_metric_query()` | [metrics docs](docs/metrics.md) |
| **Contract-based quality** — every model has a Soda contract gated as a Dagster asset check | `soda/contracts/` + Soda asset checks that block downstream materialization on failure | [ticket:observability-pass](.loom/tickets/20260420-wvp3m9gt-observability-pass.md) · [contracts doc](docs/contracts.md) |
| **Schema-contract CI gate** — breaking changes to contracts require explicit opt-in | `scripts/schema_gate.py` runs on PRs, blocks column drops / type narrowings without `accept-breaking-change` marker | [ticket:schema-contract-ci](.loom/tickets/20260420-bsha1b91-schema-contract-ci.md) |
| **Auto-generated data dictionary** — every model's columns, types, checks, and lineage discoverable without cloning | [doctacon.github.io/databox](https://doctacon.github.io/databox/), regenerated from `sqlmesh.Context` + Soda YAML | [ticket:data-dictionary-site](.loom/tickets/20260420-2ikjh1e2-data-dictionary-site.md) |
| **Idempotent incremental ingest** — reruns do not double-count | Merge keys are declared; Quack append-loads are deduplicated post-load by the same keys | [ticket:incremental-load-audit](.loom/tickets/20260420-c1ogpdel-incremental-load-audit.md) · [incremental-loading doc](docs/incremental-loading.md) |
| **Single-file local warehouse** — one reproducible data and application-state database | Quack-backed dlt sources and SQLMesh models share `data/databox.duckdb` | [ADR-0007](docs/adr/0007-quack-single-file-local-ingest.md) |
| **Single orchestration surface** — Dagster owns every run, no CLI drift | Every asset (ingest, transform, quality) visible in one DAG; `task` targets are thin wrappers | [ADR-0005](docs/adr/0005-dagster-as-sole-orchestrator.md) |

## Stack

- **[dlt](https://dlthub.com/)** — Python-native ingestion, auto-schema inference
- **[SQLMesh](https://sqlmesh.com/)** — SQL transforms with virtual environments, native metrics, column-level change detection (see [ADR-0002](docs/adr/0002-sqlmesh-over-dbt.md))
- **[DuckDB](https://duckdb.org/)** — embedded analytical warehouse (see [ADR-0001](docs/adr/0001-duckdb-as-primary-warehouse.md))
- **[Dagster](https://dagster.io/)** — sole orchestrator; assets, schedules, sensors, asset checks (see [ADR-0005](docs/adr/0005-dagster-as-sole-orchestrator.md))
- **[Soda Core](https://www.soda.io/soda-core)** — contract-based quality, run as asset checks
- **[MkDocs-Material](https://squidfunk.github.io/mkdocs-material/)** — auto-generated data dictionary site

## Architectural decisions

Six backfilled ADRs (Nygard format) cover the choices that load-bear on
the rest of the design. Each one is under 200 lines.

- [ADR-0001](docs/adr/0001-duckdb-as-primary-warehouse.md) — DuckDB as the primary warehouse
- [ADR-0002](docs/adr/0002-sqlmesh-over-dbt.md) — SQLMesh over dbt
- [ADR-0003](docs/adr/0003-single-sqlmesh-project.md) — Single SQLMesh project across all sources
- [ADR-0004](docs/adr/0004-per-source-raw-catalogs.md) — Per-source raw DuckDB catalogs (legacy local fallback)
- [ADR-0005](docs/adr/0005-dagster-as-sole-orchestrator.md) — Dagster as the sole orchestrator
- [ADR-0006](docs/adr/0006-motherduck-as-cloud-path.md) — Superseded cloud path (historical)
- [ADR-0007](docs/adr/0007-quack-single-file-local-ingest.md) — Quack single-file local ingest

## Quickstart

```bash
# Install (requires uv plus Node.js/npm for the React app)
task install

# Configure source keys plus Cloudflare Workers AI for the local trip planner
cp .env.example .env && $EDITOR .env

# Run everything headlessly (ingest → transform → quality)
task full-refresh

# Or interactive: Dagster UI at localhost:3000
task dagster:dev

# Edit a model? Propose in dev, verify, promote to prod
task plan:dev      # materialize into ebird__dev, noaa__dev, ...
task verify:dev    # Soda contracts run against __dev schemas
task plan:prod     # promote verified changes — see docs/environments.md

# Optional: verify the configured agent model (@cf/zai-org/glm-5.2)
task smoke:cloudflare-ai

# Launch the local Trip Planner (FastAPI + React) at localhost:5173
task app:dev

# Or build and serve it from one local process at localhost:8000
task app

# Re-audit an existing browser build for configured Cloudflare names/values
task app:audit-bundle
```

Dagster owns source ingestion as independent jobs (`ebird_ingest`,
`gbif_ingest`, `xeno_canto_ingest`, `noaa_ingest`, `usgs_ingest`, and
`usgs_earthquakes_ingest`) plus schedules, sensors, and asset checks.
`task full-refresh` starts one Quack server, launches all registered source jobs
concurrently as hermetic clients, stops/deduplicates the warehouse, then invokes
native SQLMesh only after every source succeeds. See
[ADR-0005](docs/adr/0005-dagster-as-sole-orchestrator.md) and
[ADR-0007](docs/adr/0007-quack-single-file-local-ingest.md).

Per-mart staleness SLAs are declared in each domain module and validated
by `last_update` asset checks; a sensor emits a structured warning line
per violation. See [docs/freshness.md](docs/freshness.md).

Local recovery scenarios — blown DuckDB file, partial source
backfill, and paused-schedule resumption
— have copy-pasteable recovery commands in
[docs/runbook.md](docs/runbook.md).

## Forking

Databox is designed to be forked. After cloning:

```bash
task init -- \
  --name Weatherbox --slug weatherbox \
  --org your-org --repo weatherbox \
  --site-url https://your-org.github.io/weatherbox/
```

`task init` reads `scaffold.yaml`, rewrites every project-identity reference across README/mkdocs/docs/LICENSE/pyproject, and is a no-op on second run. The three example sources (eBird / NOAA / USGS) stay wired so the whole pipeline is green on day one — delete or replace them at your own pace.

See **[docs/template.md](docs/template.md)** for the full list of what's covered, what stays unchanged (Python package name, external deps), and how to extend the scaffold.

## Local warehouse

Databox uses one Quack-backed `data/databox.duckdb` file for raw schemas,
SQLMesh models, and persisted application artifacts. `databox.config.settings`
is the single source of truth for the local path and Soda datasource. See
[docs/configuration.md](docs/configuration.md),
[docs/secrets.md](docs/secrets.md), and
[ADR-0007](docs/adr/0007-quack-single-file-local-ingest.md).

## Repository layout

```
packages/                  # uv workspace
├── databox/               # Shared library (config / quality / orchestration)
└── databox-sources/       # dlt ingestion + per-source configs

transforms/main/           # Unified SQLMesh project (ADR-0003)
├── config.py              # local SQLMesh gateway
├── metrics/               # semantic metrics registry
└── models/
    ├── environmental_observations/ # CDM dimensions + facts
    └── analytics/                  # operational platform health

soda/contracts/            # Soda contracts for raw, CDM, and operational models

docs/
├── adr/                   # 6 backfilled ADRs
├── dictionary/            # Auto-generated by scripts/generate_docs.py
└── {metrics,contracts,...}.md

scripts/
├── generate_docs.py       # Data-dictionary generator
├── generate_staging.py    # Staging-SQL codegen from Soda contracts
├── schema_gate.py         # CI breaking-change gate
└── check_source_layout.py # Source-layout convention lint

data/                      # DuckDB files (gitignored)
```

Adding a source? See [docs/new-source.md](docs/new-source.md) and then extend the `.schema` CDM workflow before adding SQLMesh models.

## Published artifacts

- **Data dictionary + lineage:** https://doctacon.github.io/databox/ — regenerates on every push to `main`
- **[docs/metrics.md](docs/metrics.md)** — semantic metrics registry and `resolve_metric_query` helper
- **[docs/analytics-examples.md](docs/analytics-examples.md)** — representative queries against the CDM model layer
- **[docs/contracts.md](docs/contracts.md)** — Soda contract conventions + schema-contract gate escape hatch
- **[docs/incremental-loading.md](docs/incremental-loading.md)** — per-resource write disposition, keys, backfill

## Observability

Two surfaces ship in-tree: the Dagster UI (asset graph, asset checks,
freshness panel) and the auto-generated data dictionary at
https://doctacon.github.io/databox/.

For external lineage catalogs, Dagster attaches an OpenLineage-emitting
sensor when `OPENLINEAGE_URL` is set in `.env`. Every major catalog
(Marquez, DataHub, OpenMetadata, Atlan, Astro) speaks OpenLineage, so
forkers drop whichever URL they already have and restart Dagster — no
code change. Install with `uv sync --package databox --extra lineage`.
Full walkthrough + local Marquez docker-compose in
[docs/observability.md](docs/observability.md).

## Development

```bash
task install         # Install dependencies (uv sync + pre-commit hook)
task verify          # Smoke full-refresh via Dagster (DATABOX_SMOKE=1)
task ci              # Ruff + mypy + pytest + secret scan
```

Raw lint / format / test / SQLMesh / Dagster CLIs are in
[docs/commands.md](docs/commands.md). `Taskfile.yaml` deliberately
keeps only targets that compose multiple commands or inject env vars.

## License

MIT — see [LICENSE](LICENSE).
