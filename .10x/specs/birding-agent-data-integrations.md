Status: active
Created: 2026-07-08
Updated: 2026-07-08

# Birding Agent Data Integrations

## Purpose and scope

This spec governs the first data-integration slice for the Birding Trip Copilot. It covers how Databox should add and use GBIF, Xeno-canto, and Open-Meteo alongside existing eBird/NOAA/USGS data.

## Existing authoritative context

- dlt remains the ingestion layer for durable source data.
- SQLMesh remains the transformation/modeling layer.
- Dagster remains the orchestrator for dlt ingestion, schedules, sensors, and checks.
- Local Quack-backed DuckDB remains the default local warehouse path.
- Source domains are ingestion-only; cross-source CDM/planner modeling belongs in SQLMesh/analytics wiring.

## Source responsibilities

### GBIF

GBIF SHOULD provide occurrence/taxonomy context for bird species beyond the current eBird recent-observation slice.

The GBIF integration SHOULD land durable source data through dlt into a `raw_gbif` schema, unless implementation research proves the first endpoint should remain a live tool. If GBIF credentials are required for a chosen endpoint, they MUST be read from environment variables and MUST NOT be written into `.10x`, logs, tests, fixtures, or generated docs.

The GBIF integration MUST preserve source identifiers, scientific names, taxonomic identifiers where available, event/observation dates where available, coordinates/region where available, basis/status fields where available, and source/provenance metadata needed to explain recommendations.

### Xeno-canto

Xeno-canto SHOULD provide bird-call/media metadata and source links for recommended species.

The Xeno-canto integration SHOULD land durable metadata through dlt into a `raw_xeno_canto` schema. The MVP MUST treat media as linked external artifacts with license/provenance metadata; it MUST NOT bulk-download audio unless a later explicit ticket ratifies storage, licensing, and retention behavior.

The integration MUST preserve species names/codes, recording IDs or URLs, quality/rating fields where available, location/date metadata where available, license fields where available, and attribution/provenance metadata.

### Open-Meteo

Open-Meteo SHOULD provide request-time weather forecast and elevation context for a specific trip location/time.

Because trip planning needs dynamic user-selected locations and future windows, the MVP SHOULD implement Open-Meteo as an agent tool rather than a scheduled dlt pipeline. The tool MUST persist the weather/elevation response used for each trip plan into the trip-plan evidence artifacts so the plan remains reproducible.

A later dlt cache/history pipeline MAY be added only after retention, query grain, and use cases are ratified.

## Modeling expectations

SQLMesh models SHOULD expose planner-ready views/tables that make the agent tools simple and deterministic. The model layer SHOULD avoid model-generated inferred attributes that are not present in sources or ratified use cases.

Planner-ready models SHOULD support:

- species/taxonomy lookup,
- recent observation lookup,
- occurrence or historical context lookup,
- media lookup with license/provenance,
- persisted trip-plan evidence and trace queries.

## Quality and provenance

Every new durable source integration MUST include:

- a documented source layout,
- a raw source schema annotation step once data exists,
- source freshness/availability handling where applicable,
- tests for source parsing and stable schemas,
- data-quality checks sufficient to catch missing core identifiers.

## Acceptance criteria

- GBIF and Xeno-canto source data can be loaded locally through the established dlt/Quack/Dagster path.
- Open-Meteo weather/elevation context can be retrieved for a requested trip location/time and persisted as trip evidence.
- New raw schemas do not break existing `task verify`, `task ci`, or existing source jobs.
- Planner-ready SQL interfaces exist for species/occurrence/media/weather evidence needed by `.10x/specs/birding-trip-copilot.md`.
- Source provenance and license/attribution fields are preserved where upstream APIs provide them.
