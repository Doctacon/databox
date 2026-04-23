---
id: plan:staff-portfolio-readiness
kind: plan
status: active
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-21T21:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  constitution: constitution:main
---

# Sequencing

Four phases. Each phase's tickets can run in parallel internally; phases are ordered because later work assumes earlier foundations.

## Phase 1 — Reliability foundation

Runs first. Everything else rides on this.

- ticket:ci-github-actions — GitHub Actions pipeline (lint, typecheck, SQLMesh plan, Soda validate, tests)
- ticket:source-test-harness — Unit + integration tests for dlt sources with recorded fixtures
- ticket:observability-pass — Structured logging, Dagster freshness policies, asset SLA metadata

## Phase 2 — Data governance

Depends on CI existing so contracts can gate.

- ticket:schema-contract-ci — Breaking-change detection on SQLMesh plans and Soda schema drift
- ticket:data-dictionary-site — Generated static data dictionary + column-level lineage site

## Phase 3 — Cross-domain value

Depends on governance so the mart is trustable.

- ticket:flagship-cross-domain-mart — `analytics.fct_species_weather_streamflow_daily` or equivalent
- ticket:semantic-metrics-layer — SQLMesh metrics (or thin alternative) for the flagship domain
- ticket:incremental-load-audit — Document and test merge strategy, idempotency, backfill per source

## Phase 4 — Portfolio polish

Lands last. Describes what now exists.

- ticket:architecture-docs — Mermaid C4 + data flow diagrams, ADR backfill, case-study README

## Phase 5 — Post-review hardening

Opened 2026-04-21 after a staff-lens self-review surfaced drift, scaffold leaks, test gaps, and absent-deploy problems. Each ticket addresses one specific finding a staff DE reviewer would poke at within the first ten minutes of reading the repo. Phase 5 tickets are loosely dependent on each other — they can run in any order, with the exception that ticket:scaffold-hardcoded-source-list and ticket:sqlmesh-test-depth both benefit from ticket:docs-drift-purge landing first so commits don't fight over the same README lines.

- ticket:docs-drift-purge — eliminate stale CLI references in CLAUDE.md, delete phantom `transforms/CLAUDE.md`, fix README mermaid diagrams to remove deleted notebook nodes
- ticket:scaffold-hardcoded-source-list — replace hardcoded `("ebird","noaa","usgs")` tuples across `_factories.py` / `settings.py` / `smoke.py` / `platform_health.sql` with a single source registry so the 4th source (usgs_earthquakes) actually participates in every code path that claims to be dataset-agnostic
- ticket:sqlmesh-test-depth — bring SQLMesh unit-test count from 5 to ≥20, with special-case coverage for the flagship cross-domain mart's windowed anomaly math
- ticket:dagster-deploy-live — stand up a live Dagster deployment (Dagster Cloud Serverless / Fly / Render) and link its URL from the README
- ticket:loom-ledger-audit — reconcile status-field drift across initiatives/plans/tickets, add a CI validator that enforces cross-layer state coherence
- ticket:mypy-strict-gate — drop `--ignore-missing-imports`, adopt per-package strict mypy, add a 70% coverage floor in CI
- ticket:overengineering-trim — write ADR-0007 documenting the explicit keep/cut decisions for OpenLineage, the freshness violation sensor, Dive preview, and the Streamlit explorer
- ~~ticket:cost-rate-dynamic~~ — closed 2026-04-22 without implementation; operator runs on MotherDuck free tier, so per-compute-second rate staleness warnings would track a number nobody pays
- ticket:dual-consumer-surface — pick Streamlit, Dive, or both-with-explicit-roles as the canonical consumer surface and document the decision (+ ADR if Dive is kept, since it overrides the open-source-first principle)

# Dependencies

- Phase 2 assumes Phase 1 CI exists (contract checks are CI steps)
- Phase 3 flagship mart assumes source tests (Phase 1) and schema contracts (Phase 2) so changes don't silently corrupt it
- Phase 4 demo ticket assumes the flagship mart exists so the dashboard has something to show
- Phase 5 assumes Phases 1-4 are landed (they are). No hard ordering inside Phase 5 except the docs-drift-purge soft-dependency noted above.

# Out of Scope

- Streaming/CDC sources
- Reverse ETL
- Cost tracking dashboards (nice-to-have, deferred)
- Multi-repo splitting
