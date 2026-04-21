---
id: plan:staff-portfolio-readiness
kind: plan
status: active
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T00:00:00Z
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

# Dependencies

- Phase 2 assumes Phase 1 CI exists (contract checks are CI steps)
- Phase 3 flagship mart assumes source tests (Phase 1) and schema contracts (Phase 2) so changes don't silently corrupt it
- Phase 4 demo ticket assumes the flagship mart exists so the dashboard has something to show

# Out of Scope

- Streaming/CDC sources
- Reverse ETL
- Cost tracking dashboards (nice-to-have, deferred)
- Multi-repo splitting
