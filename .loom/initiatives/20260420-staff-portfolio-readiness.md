---
id: initiative:staff-portfolio-readiness
kind: initiative
status: active
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T00:00:00Z
scope:
  kind: workspace
links:
  constitution: constitution:main
---

# Outcome

Databox becomes a portfolio artifact that credibly signals staff-level data engineering: production reliability, data governance, cross-domain analytical value, performance/cost awareness, and a narrative a hiring manager can skim in ten minutes.

# Why Now

Current state is a well-architected hobby platform — dlt + SQLMesh + DuckDB + Dagster + Soda, dual-backend, constitution-grounded. Strong bones, but a recruiter reviewing the repo cold would not see:

- CI enforcing contracts, tests, and lint on every change
- Source and pipeline test coverage
- Observability beyond Dagster defaults (SLAs, freshness policies, structured logs)
- Data contracts gating breaking schema changes
- A published data dictionary / lineage surface
- A flagship cross-domain mart demonstrating the "analytics is the point" claim from the constitution
- Documented incremental-load and idempotency guarantees per source
- A one-command demo environment and a case-study README

These are the standard staff-level signals: systems thinking, reliability culture, governance, and the ability to turn raw sources into cross-domain product value.

# Strategic Frame

- Reliability and governance land first — they compound. Every later ticket runs against that foundation.
- Cross-domain value (flagship mart + semantic layer) is the "what does this actually do" payoff.
- Portfolio polish lands last, after the substance it describes exists.
- No managed-service additions. All tickets respect the constitution's open-source-first and zero-infra-default constraints.

# Non-Goals

- Multi-tenant features, RBAC, SaaS framing
- Rewriting the stack (dlt/SQLMesh/Dagster/Soda stay)
- Streaming/CDC ingestion (deferred — out of scope for this initiative)
- Hand-rolled orchestration outside Dagster

# Success Criteria

- CI runs on every PR and blocks on lint, typecheck, SQLMesh plan, Soda contract validation, and source tests
- Every dlt source has unit tests against recorded API fixtures; Dagster assets have at least smoke tests
- Every mart has a published freshness SLA and an observable asset-check outcome
- Breaking schema changes (column drops, type changes) fail CI unless explicitly approved
- At least one flagship cross-domain mart exists in `analytics`, with a semantic/metrics surface
- A static data dictionary + lineage site is generated from SQLMesh + Soda metadata
- Architecture docs, diagrams, and a case-study README exist at repo root
- One-command local bring-up works (`task demo` or Docker Compose) and produces the flagship dashboard

# Planned Work

See plan:staff-portfolio-readiness for sequencing.
