Status: active
Created: 2026-09-03
Updated: 2026-09-03

# Databox–Rufous data-product boundary

## Purpose

Define the only supported runtime boundary between Databox and the standalone Rufous product.

## Databox responsibilities

Databox MUST retain source implementations, raw Polaris Iceberg authority, Dagster source orchestration, generic environmental models, platform health, and reusable source quality controls. This includes eBird, GBIF, Xeno-canto, AVONET, USFWS, NOAA, USGS, and earthquake ingestion.

Databox MUST produce a bounded versioned DuckDB artifact containing only explicitly contracted modeled relations required by Rufous. Export MUST be deterministic, atomic, read-only to consumers, schema-versioned, and fail closed when required relations or contract checks are absent. It MUST NOT include personal application state, secrets, raw credentials, unrestricted private locations, or unrelated platform schemas.

`databox-sources` MUST expose the USFWS source through a documented stable public import. Rufous MAY pin that package by immutable Git tag or commit. Databox MUST NOT derive Rufous-specific USFWS target semantics after extraction.

## Rufous responsibilities

Rufous MUST own the `birding_agent` and `rufous_public` transformation schemas, product APIs and agents, local application state, web application, public export/media pipelines, public and private deployment workflows, and product-specific contracts/tests/docs.

Rufous MUST consume the Databox artifact through an explicit configured path and attach it read-only. It MUST use a separate writable application database. It MUST NOT import private `databox` modules or assume Databox repository-relative paths.

Rufous MUST own USFWS target derivation and its manual unscheduled workflow. Targets MUST remain fail-closed and the workflow MUST preserve current licensing, identity, bounded-request, current-run, approval, and publication rules.

## Model ownership

- Databox: `environmental_observations/*`, `analytics.platform_health`.
- Rufous: `birding_agent/*`, `rufous_public/*`.

When a moved model currently depends on a Databox relation, that relation MUST either be included in the versioned artifact contract or the dependency MUST be redesigned explicitly; it MUST NOT be silently copied.

## Acceptance scenarios

- Given only a released Databox artifact and the pinned public `databox-sources` dependency, Rufous can run its credential-free tests without a Databox checkout.
- Given only Databox, all retained platform ingestion, transformation, documentation, and tests pass without Rufous code or workflows.
- Either repository can release without checking out the other repository.
- Contract mismatch produces a legible version/schema error before product execution.

## Explicit exclusions

- Shared mutable DuckDB files.
- Runtime HTTP coupling between the repositories.
- Copied Databox internals.
- Automatic USFWS schedules.
- Production deployment enablement during extraction.
