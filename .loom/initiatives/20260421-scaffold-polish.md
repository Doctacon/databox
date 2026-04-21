---
id: initiative:scaffold-polish
kind: initiative
status: active
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  constitution: constitution:main
---

# Outcome

Databox becomes the ultimate starting-point scaffold for a brand-new single-operator data project. Someone can fork the repo, replace the three baked-in sources with their own in under a day, and inherit a production-quality stack with CI, contracts, lineage, metrics, ADRs, and a published data dictionary — without adopting any convolution the maintainer would regret at 20 sources.

# Why Now

`initiative:staff-portfolio-readiness` shipped all four phases (flagship mart, semantic metrics, dictionary site, ADR-backed README). The repo is now a credible portfolio artifact. But two things are true at the same time:

1. **It is not yet a template.** `Doctacon/databox` URLs, eBird/NOAA/USGS identity, and a five-step manual "add a new source" process are baked into the shape. A fork cannot cleanly evolve into a different domain.
2. **It has accumulated scaffolding convolution.** Four uv packages for ~35 Python files, a 469-line single-file `definitions.py`, a 288-line `schema_gate.py` reimplementing Soda-adjacent logic, seven trivial-rename staging models, fragmented config across six surfaces, a 224-line Taskfile that mostly wraps `dagster`/`sqlmesh` CLI one-for-one.

Both are solvable. Simplification must come before the template work — otherwise the generator templates the wrong shape.

# Strategic Frame

- **Simplify first, codify second, scaffold third.** Shrink the convolutions, then lock a per-source layout convention, then build the generator on top.
- **Per-source surface must stay crisp.** A new source = one ingest module + one SQL directory + one Soda-contract directory + one Dagster domain file. Shared code (config, quality engine, orchestration infra) consolidates once, does not grow with N sources.
- **Operability last.** Freshness SLAs, cost observability, and DR runbooks describe how to run the template in production — they ride on the stabilised shape.
- **No new managed services.** Constitution's open-source-first and zero-infra-default constraints stand.

# Non-Goals

- Multi-tenant, RBAC, SaaS framing
- Rewriting the stack (dlt / SQLMesh / DuckDB / Dagster / Soda stay)
- Streaming or CDC ingestion
- A separate "databox-cli" resurrection — Dagster remains the single entrypoint per ADR-0005
- Packaging databox as a PyPI-published library (it is a template, not a dependency)

# Success Criteria

- **Fork-to-first-pipeline under one day.** Clone, `task init` with a project name and one source config, `task full-refresh` produces a mart and a dictionary page for the new source.
- **One `databox` Python package.** `databox-config`, `databox-quality`, and `databox-orchestration` collapse into `databox/{config,quality,orchestration}/`. `databox-sources` stays separate because the registry pattern scales with source count.
- **Per-source layout is lint-enforced.** `scripts/check_source_layout.py` runs in CI and fails a PR that adds a source missing any of: ingest module, staging SQL, marts SQL, Soda contract, Dagster domain file.
- **Staging models are generated, not hand-written** for the trivial-rename case.
- **Config has one source of truth.** A single Pydantic settings object drives dlt, SQLMesh gateways, Soda datasources, and Dagster resources. Other files reference it; none duplicate it.
- **`definitions.py` splits per domain.** Root file globs `databox/orchestration/domains/*.py` and assembles the Dagster `Definitions`.
- **Taskfile ≤100 lines.** Each target justifies its existence — no one-for-one wrappers around `dagster`/`sqlmesh` CLI.
- **`schema_gate.py` ≤80 lines.** The 288-line classifier becomes a thin wrapper around SQLMesh plan JSON + Soda contract-diff primitives.
- **`scripts/new_source.py`** scaffolds a new source directory tree and Dagster domain file from a name + API-shape template.
- **Path-based CI.** Only jobs relevant to the changed files run; full matrix only on `main` or when the CI config itself changes.
- **Flagship freshness SLA is wired and firing** via Dagster `build_last_update_freshness_checks`.
- **Backfill + DR runbook exists** at `docs/runbook.md` covering blown DuckDB file, partial backfill, MotherDuck point-in-time recovery.
- **Example consumer notebook** at `notebooks/metrics_demo.ipynb` runs end-to-end against the flagship mart using the metrics helper.
- **Cost observability panel** — daily MotherDuck usage summary either in Dagster metadata or `docs/cost.md` auto-updated by a scheduled asset.
- **Secrets pluggability documented.** `.env` stays default; `docs/secrets.md` documents the integration points for 1Password / Vault / AWS Secrets Manager.

# Planned Work

See plan:scaffold-polish for sequencing.
