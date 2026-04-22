# Observability

Databox ships two observability surfaces out of the box:

1. **Dagster UI** — built-in asset graph, run history, asset check panel,
   and freshness view. Launch with `task dagster:dev`.
2. **Data dictionary site** — static MkDocs build under `docs/dictionary/`,
   auto-generated from SQLMesh + Soda metadata. Covered in the
   [data dictionary](dictionary/index.md) section.

Beyond the built-ins, the stack opts in to external lineage catalogs via
OpenLineage. This page covers that plumbing.

## External lineage catalogs (OpenLineage)

[OpenLineage](https://openlineage.io/) is the open standard for emitting
metadata about data pipelines as they run. Every major data catalog
(DataHub, OpenMetadata, Atlan, Marquez, Astro, Unity Catalog) understands
OpenLineage events natively. Lighting up the emitter once makes the
project portable across all of them — Forker drops the right URL in
`.env` and lineage appears in whichever tool they already run.

### How it works

Dagster has the asset graph. OpenLineage's Dagster sensor walks Dagster's
event log and emits one of:

- **RunEvent** — when an asset materialization starts / completes / fails
- **JobEvent** — the asset graph that ran
- **DatasetEvent** — the input and output datasets touched by the run

No configuration beyond three env vars. The sensor ships disabled when
`OPENLINEAGE_URL` is unset, so the default experience costs nothing.

### Enable it

```bash
# 1. Install the optional extra (ships openlineage-python + openlineage-dagster).
uv sync --extra lineage

# 2. Point at a backend. Pick one:
#    - Local Marquez:  http://localhost:5000
#    - Self-hosted DataHub:  http://datahub:8080/openapi/openlineage/api/v1/lineage
#    - Managed Astro / Atlan / OpenMetadata: whatever URL the vendor gives you

echo 'OPENLINEAGE_URL=http://localhost:5000' >> .env
echo 'OPENLINEAGE_NAMESPACE=databox' >> .env

# 3. Restart Dagster.
task dagster:dev
```

Materialize any asset. Events start landing in the backend within a few
seconds of the run completing.

### Disable it

Unset `OPENLINEAGE_URL` in `.env` (or comment it out). The sensor falls
away on the next Dagster restart — no stale state, no warnings.

### Run Marquez locally (zero-cost option)

Marquez is the reference OpenLineage backend. Docker compose brings up
the API + UI in under a minute.

```yaml
# docker-compose.marquez.yaml
version: "3.7"
services:
  marquez:
    image: marquezproject/marquez:latest
    ports:
      - "5000:5000"   # OpenLineage HTTP API
      - "3000:3000"   # Web UI
    environment:
      MARQUEZ_PORT: 5000
      MARQUEZ_ADMIN_PORT: 5001
      POSTGRES_HOST: marquez-db
      POSTGRES_USER: marquez
      POSTGRES_PASSWORD: marquez
    depends_on:
      - marquez-db
  marquez-db:
    image: postgres:14
    environment:
      POSTGRES_USER: marquez
      POSTGRES_PASSWORD: marquez
      POSTGRES_DB: marquez
```

```bash
docker compose -f docker-compose.marquez.yaml up -d
open http://localhost:3000   # Marquez UI
```

With `OPENLINEAGE_URL=http://localhost:5000` set, a
`task full-refresh` run shows up as a job in Marquez with inputs, outputs,
and the dataset graph.

### Pointing at something else

The OpenLineage client reads three environment variables directly; the
values in `DataboxSettings` are mirrored only so `.env` is the one place
operators look:

| Var | What it does |
| --- | --- |
| `OPENLINEAGE_URL` | Collector endpoint. Setting this is the on-switch. |
| `OPENLINEAGE_NAMESPACE` | Logical namespace in the catalog (default `databox`). |
| `OPENLINEAGE_API_KEY` | Bearer token for SaaS backends (Astro, Atlan, managed DataHub). |

## Freshness + violations

Covered in [freshness.md](freshness.md). The freshness sensor emits a
structured log line per check failure; wire that into Slack / PagerDuty
via Dagster's standard sensor-action hooks.
