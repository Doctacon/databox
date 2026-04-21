---
id: ticket:unify-config-surface
kind: ticket
status: complete_pending_acceptance
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 1
depends_on:
  - ticket:collapse-packages
---

# Goal

Make one Pydantic settings object the single source of truth for every runtime configuration decision. dlt, SQLMesh, Soda datasources, Dagster resources, and Taskfile variables all read from it. No other file duplicates values it owns.

# Why

Today the runtime config surface is spread across:

- `packages/databox-config/databox_config/settings.py` (Pydantic `Settings`)
- root `pyproject.toml`
- per-package `pyproject.toml` (×4)
- `Taskfile.yaml`
- `transforms/main/config.yaml` (SQLMesh gateways)
- `soda/datasources/*.yml` (Soda connection config)
- `.dlt/secrets.toml` or `.env` (dlt-pipeline side)
- hard-coded defaults scattered in Dagster resource definitions

The DuckDB path, the MotherDuck token, and the backend selector are repeated in 3–4 of those surfaces each. A fork that changes any of them has to update every surface or find out at runtime which one won.

A single settings object — already partially present in `databox.config.settings` post–collapse-packages — should own those values and render the other files (SQLMesh `config.yaml`, Soda `datasources/*.yml`) from it when they need to be on-disk.

# In Scope

- Audit every config-bearing file and classify each setting as:
  - **authoritative** (lives in `Settings`)
  - **rendered** (generated from `Settings` at build time or runtime)
  - **legitimately separate** (e.g. `pyproject.toml` build metadata)
- Extend `databox.config.Settings` to cover:
  - backend selector (`local` / `motherduck`)
  - DuckDB file paths (computed)
  - MotherDuck URIs (computed)
  - SQLMesh gateway name (computed from backend)
  - Soda datasource name + connection dict (computed)
  - dlt destination config (computed)
  - per-source API tokens (already present; audit for completeness)
- Render `transforms/main/config.yaml` from a template + settings if the file needs to exist on disk, or load programmatically at SQLMesh entry point
- Render `soda/datasources/*.yml` similarly
- Update Dagster resources to read exclusively from the settings object
- Remove any hardcoded defaults elsewhere; replace with `Settings` field lookups
- Document the authoritative surface in `docs/configuration.md`

# Out of Scope

- Refactoring the Pydantic version (stay on whichever major is pinned)
- Migrating secrets off `.env` to Vault / 1Password — that is ticket:secrets-pluggable
- Changing backend behaviour — this is a plumbing ticket, not a feature ticket

# Acceptance Criteria

- `databox.config.Settings` is the only place where any runtime value is declared
- `rg -n 'DUCKDB_PATH|MOTHERDUCK_TOKEN|DATABOX_BACKEND' packages transforms soda Taskfile.yaml` shows references only — no hardcoded equivalents
- Changing `DATABOX_BACKEND=motherduck` in `.env` flips SQLMesh gateway, Soda datasource, and Dagster resources without touching any other file
- `docs/configuration.md` documents the authoritative surface and the rendered files
- Existing full-refresh (`task full-refresh`) works on both backends after the refactor
- MkDocs strict build clean with the new `configuration.md` in nav

# Approach Notes

- Prefer `@computed_field` on the Pydantic model over separate helper functions for derived values
- SQLMesh's `config.yaml` supports Python-loaded config via `sqlmesh.core.config.Config` — use that instead of rendering YAML when possible; it avoids a stale-file class of bug
- Soda's `datasources.yml` needs the file on disk; render it via a small `scripts/render_soda_config.py` called from the Taskfile or a Dagster init resource
- Watch out for `sqlmesh` CLI which resolves `config.yaml` itself — if we go Python-loaded, the CLI invocations need to point at the module

# Evidence Expectations

- Before/after `rg` output showing config values exist in exactly one place
- Round-trip test: flip `DATABOX_BACKEND`, run the flagship asset, contract check passes on both backends
- `docs/configuration.md` rendered in the deployed docs site
