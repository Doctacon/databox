# Orchestration

Dagster-based orchestration that auto-generates assets from the pipeline registry.

## How it works

`dagster_project.py` reads all registered pipelines from `config/pipelines/*.yaml` and dynamically generates:

- **Ingestion assets** — one per pipeline, runs `source.load()`
- **Transform assets** — one per pipeline with a `transform_project`, runs sqlmesh
- **Jobs** — one per pipeline, combining ingestion + transform assets
- **Schedules** — one per enabled pipeline, using the cron from config

Adding a new source to the registry automatically creates its Dagster assets with zero code changes here.

## Running

```bash
# Install orchestration dependencies
task install-orchestration

# Start Dagster dev server
task dagster:dev
```

## Configuration

Pipeline schedules are defined in `config/pipelines/<source>.yaml`:

```yaml
schedule:
  cron: "0 6 * * *"
  enabled: true
```

Set `enabled: false` to disable scheduling for a pipeline without removing it from the graph.
