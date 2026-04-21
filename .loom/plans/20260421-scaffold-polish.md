---
id: plan:scaffold-polish
kind: plan
status: active
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  constitution: constitution:main
---

# Sequencing

Three phases. Phase 1 simplifies and locks per-source convention. Phase 2 builds the template ergonomics on top of the stabilised shape. Phase 3 adds production operability.

Within a phase, listed order reflects dependency. Tickets without inter-dependencies can run in parallel.

## Phase 1 — Simplify and lock convention

Must ship before Phase 2. The generator would template the wrong shape otherwise.

1. ticket:collapse-packages — fold `databox-config` / `databox-quality` / `databox-orchestration` into a single `databox` package. `databox-sources` stays separate (registry scales with N).
2. ticket:unify-config-surface — one Pydantic settings object is the single source of truth. dlt, SQLMesh, Soda, Dagster resources all read from it.
3. ticket:definitions-split — break the 469-line `definitions.py` into per-domain files under `databox/orchestration/domains/`, glob-loaded at the root.
4. ticket:taskfile-trim — cut Taskfile to ≤100 lines. Remove one-for-one CLI wrappers. Keep targets that compose.
5. ticket:schema-gate-library-refactor — rewrite `schema_gate.py` as a thin wrapper around SQLMesh plan JSON and Soda contract-diff primitives. Target ≤80 lines.
6. ticket:staging-model-codegen — generate trivial-rename staging models from Soda contracts. Hand-written escape hatch preserved for non-trivial cases.
7. ticket:source-layout-convention — codify the per-source directory contract. `scripts/check_source_layout.py` enforces it in CI.
8. ticket:path-based-ci — only run CI jobs relevant to changed paths. Full matrix on `main` and on CI-config changes.

## Phase 2 — Scaffold ergonomics

Depends on Phase 1 being stable. The generator and bootstrap script template the layout Phase 1 locks in.

1. ticket:fork-friendly-bootstrap — extract `Doctacon/databox` and bird/weather/streamflow identity into `scaffold.yaml`. `task init` parameterises a fresh clone.
2. ticket:new-source-generator — `scripts/new_source.py` (or `task new-source -- <name>`) creates the full per-source directory tree + Dagster domain file stub.
3. ticket:secrets-pluggable — document `.env` default and integration points for 1Password / Vault / AWS Secrets Manager in `docs/secrets.md`. Settings object already supports it; doc the contract.
4. ticket:dev-prod-envs — document and wire the `plan dev` → promote → `plan prod` SQLMesh workflow. Add `task plan:dev` / `task plan:prod` targets. Per-environment gateway config.
5. ticket:example-metrics-notebook — `notebooks/metrics_demo.ipynb` runs end-to-end against the flagship mart via the metrics helper. Rendered under `docs/examples/`.

## Phase 3 — Operability

Lands last. Describes how to run the template in production.

1. ticket:freshness-slas — Dagster `build_last_update_freshness_checks` on every mart. Per-source SLA declared in `databox/orchestration/domains/<source>.py`.
2. ticket:cost-observability — daily MotherDuck usage summary emitted as Dagster asset metadata and rendered to `docs/cost.md`.
3. ticket:backfill-dr-runbook — `docs/runbook.md` covering blown DuckDB file, partial backfill, MotherDuck point-in-time recovery, schedule-paused state.

# Dependencies

- P1.2 (unify-config) rides on top of P1.1 (collapse-packages) — settings move during the collapse.
- P1.3 (definitions-split) rides on top of P1.1 — new package path.
- P1.4 (taskfile-trim) rides on top of P1.3 — some targets change invocation path.
- P1.5 and P1.6 are independent of the collapse; can start in parallel.
- P1.7 (source-layout-convention) depends on everything above landing — it codifies the stabilised shape.
- P1.8 (path-based-ci) depends on P1.7 — the path convention is what CI globs.
- P2.2 (new-source-generator) depends on P1.7 — it scaffolds the convention.
- P2.1 (fork-friendly-bootstrap) depends on P1.2 — bootstrap edits the unified config.
- P2.3, P2.4, P2.5 are independent; can run in parallel with each other and with P2.1/P2.2.
- P3.1 (freshness-slas) depends on P1.3 — SLAs declared per-domain.
- P3.2 and P3.3 are independent; can run in parallel.

# Out of Scope

- Multi-repo splitting (stays monorepo)
- Streaming / CDC sources
- Reverse ETL
- Packaging `databox` as a PyPI library
- Migrating off DuckDB / MotherDuck to a different warehouse
- Rewriting any ADR-blessed decision (ADRs 0001–0006 stand)

# Risks

- **Staging codegen regresses non-trivial staging logic.** Mitigation: escape-hatch to hand-written `stg_*.sql` is preserved; codegen only fires when the model would be a pure rename.
- **Package collapse changes import paths everywhere.** Mitigation: one big mechanical PR, not trickled. CI + mypy catch stragglers.
- **Layout lint is too strict and blocks legitimate experiments.** Mitigation: allow `# scaffold-lint: skip` marker on experimental sources; document.
- **Path-based CI misses a cross-cutting breakage.** Mitigation: full matrix still runs on `main` merges; release branches always run full matrix.
