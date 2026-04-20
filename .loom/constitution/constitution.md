---
id: constitution:main
kind: constitution
status: active
created_at: 2026-04-20T15:36:32Z
updated_at: 2026-04-20T15:36:32Z
scope:
  kind: workspace
links: {}
---

# Vision

Databox is a dataset-agnostic, single-operator data platform built from zero-cost open-source components. It ingests arbitrary sources, transforms them with versioned SQL, gates them with contract-based quality checks, and exposes them through a single orchestrated asset graph — runnable on a laptop with no infra, and promotable to cloud by flipping one environment variable.

The platform should feel like a personal data warehouse: cheap, inspectable, portable, and boring to operate.

# Principles

- **Open source first.** Every component is OSS or self-hostable. Managed/proprietary services are chosen only when no viable OSS alternative exists, and the integration surface stays small enough to swap out later.
- **Zero-infra default.** Local file-based DuckDB is the primary development target. Cloud (MotherDuck) is an opt-in via `DATABOX_BACKEND`/`DATABOX_GATEWAY`; both paths must work.
- **One orchestrator, one graph.** Dagster is the single entrypoint for ingestion, transforms, and quality. No parallel CLI/cron workflow is allowed to become the real pipeline.
- **Data flows one direction.** `raw_<source>` → `<source>_staging` → `<source>`/`analytics`. Never backwards, never across layer boundaries without an explicit model.
- **Every mart has a contract.** Each SQLMesh model has a matching Soda contract, run as a Dagster asset check after materialization. No quiet data.
- **Explicit lineage over magic.** Dagster assets and their dependencies are declared, not auto-discovered from side effects. Source registration is the one exception and is config-driven.
- **`uv` for Python, always.** All Python packaging goes through the `uv` workspace at `packages/`. No `pip install`, no `poetry`, no `conda` in this repo.
- **Secrets live in `.env`.** Never in code, never in committed config. Pre-commit hooks enforce this.
- **Research before architecture.** For specialized domains (geospatial, ML, new ingestion paradigms), research world-class patterns and present findings before committing to an approach.

# Constraints

- **No vendor lock-in in the critical path.** DuckDB file format, Parquet, and standard SQL must remain sufficient to reconstruct the platform if any hosted service disappears.
- **No proprietary clients for replaceable concerns.** e.g. MapLibre over Mapbox, PostgreSQL over Firebase, S3-compatible over vendor-only object stores.
- **Single SQLMesh project.** All sources share `transforms/main/`. Do not fork per-source SQLMesh projects — state conflicts and lineage fragmentation are worse than the coupling.
- **Raw catalogs are per-source DuckDB files.** `data/raw_<source>.duckdb` enables parallel dlt loads; do not consolidate raw into a single file.
- **No backwards compatibility shims for personal-scale churn.** Single operator — migrations and renames are cheap. Delete unused code; do not carry deprecation aliases.
- **Non-goals:** multi-tenant features, RBAC, SaaS framing, managed-service dependencies that replace the OSS core, hand-rolled orchestration outside Dagster.

# Strategic Direction

- Keep the "laptop → cloud" toggle cheap and real. Every new component must work in both backends or explicitly declare why not.
- Expand source coverage breadth-first (more domains) before depth (exotic per-source features). New sources reuse the registry pattern and the staging → mart layering.
- Grow the `analytics` schema as the cross-domain value layer. Single-source marts are plumbing; cross-domain joins are the point.
- Treat Dagster as the operator UI. Dashboards, Streamlit, and ad-hoc queries sit downstream of assets, not alongside them.
- Prefer fewer, stronger tools. Resist adding a new framework when an existing one in the stack can carry the weight.

# Current Focus

- Dagster-centric orchestration is now the only entrypoint; legacy CLI surface has been removed.
- MotherDuck cloud backend is wired and usable; per-source raw catalogs are in place.
- Dive (Vite preview environment for dashboards) is the current frontend exploration surface.
- Soda contracts cover staging and marts per source; keeping contract coverage in lockstep with new models is active work.

# Notes

- `analytics` schema should eventually split into themed sub-schemas (e.g. `analytics_ecology`, `analytics_hydrology`) once cross-domain marts grow

# Change History

- 2026-04-20 — Initial constitution drafted from README + project CLAUDE.md + parent open-source-first policy. Captures current Dagster-centric, dual-backend architecture.
