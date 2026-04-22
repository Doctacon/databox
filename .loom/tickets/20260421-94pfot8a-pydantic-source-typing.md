---
id: ticket:pydantic-source-typing
kind: ticket
status: ready
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links: {}
---

# Goal

Introduce Pydantic models at the `@dlt.resource` boundary for one source —
eBird observations — as a pilot. The resource yields validated model
instances (or validated dicts) instead of `dict[str, Any]`, and dlt
serializes them on write. Upstream schema drift (field renamed, type
flipped, field dropped) surfaces as a Pydantic ValidationError on the
offending record instead of propagating silently into DuckDB.

If the pilot proves out, subsequent tickets extend the pattern to the rest
of eBird, then NOAA, USGS, and USGS Earthquakes.

# Why

Every current resource function is typed `Iterator[dict[str, Any]]`. That
shape gives dlt total freedom to infer and evolve the warehouse schema —
great for bootstrap, bad for steady-state drift detection. When the eBird
API renamed a field, or NOAA flipped a datatype, we'd discover it via a
downstream SQLMesh test failure or a Soda contract violation hours (or
days) after the bad data landed.

Pydantic at the source boundary is the canonical fix:

- drift fails closed at extract, not at transform
- field types become a checked contract, not an implicit one
- `mypy` sees the resource shape and catches upstream/downstream mismatches
- Soda contracts become a second line of defense, not the first

dlt already supports Pydantic models — `@dlt.resource(columns=Model)` and
`yield Model(...)`. No new runtime dependency; just discipline.

Scoping the pilot to eBird observations keeps the blast radius tight and
the feedback loop fast — it's the highest-volume, most drift-prone
resource in the project.

# In Scope

- New module `packages/databox-sources/databox_sources/ebird/models.py`
  with a `RecentObservation` Pydantic model mirroring the current eBird
  recent-observations payload (typed fields, required vs optional marked).
- `recent_observations` resource in
  `packages/databox-sources/databox_sources/ebird/source.py` yields
  `RecentObservation` instances (or validated dicts via
  `RecentObservation.model_validate`), not raw dicts.
- `@dlt.resource` decorator updated to pass `columns=RecentObservation` so
  dlt takes schema from the model.
- Unit tests under `tests/` that round-trip a known-good API fixture
  through the model, plus a negative test for a drifted field (missing
  `speciesCode`, wrong type on `howMany`).
- Short doc appended to `docs/source-layout.md` or a new
  `docs/source-typing.md` describing the pattern so future sources can
  follow it.

# Out of Scope

- Adding Pydantic models to the other eBird resources (notable, species,
  hotspots, taxonomy, region_stats) — covered by a follow-up ticket once
  the pilot is accepted.
- Adding Pydantic to NOAA, USGS, or USGS Earthquakes sources — separate
  tickets.
- Generating Pydantic models from OpenAPI specs. Hand-written is fine for
  the pilot; codegen is a later optimization.
- Replacing Soda contracts. Pydantic catches type/required drift at
  extract; Soda still owns semantic contracts (row counts, freshness,
  value ranges) on the staged data.

# Acceptance

- `recent_observations` resource yields typed Pydantic instances; `mypy
  --strict` on the package is clean.
- Unit test with a fixture payload loads cleanly and materializes into a
  DuckDB table whose schema matches the model.
- Unit test with a drifted fixture (field removed, type flipped) raises
  `pydantic.ValidationError` before the record reaches dlt's writer.
- `task ci` green.
- `docs/source-layout.md` (or `docs/source-typing.md`) documents the
  pattern with an eBird example.
