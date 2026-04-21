---
id: ticket:architecture-docs
kind: ticket
status: ready
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 4
depends_on:
  - ticket:flagship-cross-domain-mart
  - ticket:observability-pass
---

# Goal

Rewrite the root README as a recruiter-oriented case study, supported by architecture diagrams, an Architecture Decision Record (ADR) backfill, and a clear "how to evaluate this repo in ten minutes" path.

# Why

A hiring manager reviews dozens of GitHub repos per week. The README is the product page. Today's README is operator-oriented ("here are the commands") rather than audience-oriented ("here is what this platform is, why it exists, and what staff-level decisions shaped it").

# In Scope

- New top-level README sections (in order):
  - One-paragraph pitch
  - System diagram (Mermaid C4 Container level)
  - Data-flow diagram (Mermaid flowchart: source → raw → staging → marts → analytics)
  - "What this demonstrates" — list of staff-level capabilities with links to the tickets/evidence proving each
  - Quickstart (existing `task` targets for Dagster + dashboard)
  - Key architectural decisions (links to ADRs)
  - Links to live docs site, dashboard, data dictionary
- `docs/adr/` directory with ADRs for:
  - Why DuckDB as primary warehouse
  - Why SQLMesh over dbt
  - Why single SQLMesh project
  - Why per-source raw catalogs
  - Why Dagster as the single orchestrator
  - Why MotherDuck as the cloud path
- Screenshots under `docs/images/` of: Dagster asset graph, asset checks panel, data dictionary site, flagship dashboard
- Badges: CI, Python version, license, docs-site

# Out of Scope

- Marketing-speak or buzzword-laden prose — keep it technical and specific
- Rewriting CLAUDE.md (operator-oriented is correct there)
- A separate marketing website

# Acceptance Criteria

- A reader who has never seen the repo can answer, within ten minutes, all of:
  - What problem does this solve
  - What is the stack and why
  - Where is the cross-domain value
  - How is quality enforced
  - How would I run it locally
- All diagrams render on GitHub directly (no external image hosting except project-hosted screenshots)
- Six ADRs exist, each under 200 lines, following the Michael Nygard format
- Badges are accurate and green

# Approach Notes

- Write the ADRs after the other initiative tickets land so decisions describe reality, not aspirations
- Keep the README under ~300 lines; push detail into `docs/`
- Lead with the diagram, not the command list
- Use active voice — "the platform ingests" not "the platform is designed to ingest"

# Evidence Expectations

- Self-review: the README addresses each of the five evaluator questions above
- Link to rendered Mermaid diagrams on GitHub
- All six ADRs merged
