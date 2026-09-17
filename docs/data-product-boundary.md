# Databox–Rufous data-product boundary

Databox and Rufous are separate repositories with an artifact boundary rather
than a shared runtime or database.

## Decision

Databox owns reusable source ingestion, Polaris/Iceberg raw authority, generic
environmental models, platform health, and reusable source-quality controls.
It publishes the bounded, versioned `rufous_inputs_v1` DuckDB artifact.

Rufous owns birding-product models, APIs and agents, application state, media
workflows, web deployment, and product-specific contracts. It attaches a
released Databox artifact read-only and keeps its writable application state in
a separate database.

The repositories release independently. Rufous may pin the public
`databox-sources` package by immutable Git tag or commit, but it must not import
private `databox` modules or assume Databox repository-relative paths.

## Artifact contract

The Databox exporter must be deterministic, atomic, schema-versioned, and fail
closed when required relations or contract checks are absent. The artifact
contains only explicitly contracted relations required by Rufous. It excludes
application state, secrets, credentials, unrestricted private locations, and
unrelated platform schemas.

Run the exporter after a successful refresh:

```bash
uv run python scripts/platform/export_rufous_product.py \
  --output build/rufous-inputs-v1.duckdb
```

Rufous must reject an incompatible contract or schema version before product
execution.

## Model and source ownership

- Databox owns `environmental_observations/*` and `analytics.platform_health`.
- Rufous owns `birding_agent/*` and `rufous_public/*`.
- Databox exposes USFWS through the stable public `databox_sources.usfws`
  interface.
- Rufous owns USFWS target derivation and every explicit-target run; Databox
  does not schedule or derive those product-specific targets.

When a Rufous model needs a Databox relation, that relation must be added to the
versioned artifact contract or the dependency must be redesigned explicitly.
It must not be silently copied or read from Databox's working database.

## Exclusions

- Shared mutable DuckDB files.
- Runtime HTTP coupling between the repositories.
- Direct Rufous access to raw Polaris tables.
- Copied Databox internals.
- Automatic USFWS schedules.
- Product deployment from this repository.
