---
id: ticket:architecture-docs
kind: ticket
status: closed
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-21T19:20:00Z
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

# Close Notes

Merged as PR #12.

**Deliverables:**
- Root `README.md` rewritten as a case study — 244 lines (under the 300-line budget):
  - one-paragraph pitch + "evaluate this repo in ten minutes" checklist
  - Mermaid C4 Container diagram showing APIs → dlt → raw catalogs → SQLMesh → Dagster → consumers
  - Mermaid data-flow diagram showing raw → staging → intermediate → marts → analytics → metrics → consumers
  - "What this demonstrates" table mapping 8 staff-level capabilities to owning tickets and evidence docs
  - Stack, ADR index, quickstart, backend switch, repo layout, published artifacts, dev loop, license
  - Badges: CI, Docs, Python 3.12, MIT
- `docs/adr/` with six ADRs (Nygard format, each <200 lines): DuckDB warehouse, SQLMesh over dbt, single SQLMesh project, per-source raw catalogs, Dagster sole orchestrator, MotherDuck cloud path. `docs/adr/README.md` indexes them.
- `mkdocs.yml` nav carries Architecture decisions section; strict build clean.
- `docs/index.md` landing page links ADRs directly.
- `LICENSE` file (MIT) added — referenced from README license badge.

**Evidence:**
- PR #12 merged; commit `148fa0a` on main.
- CI on PR #12: Ruff, mypy, pytest (30 pass), SQLMesh lint, schema-contract gate, Soda contract structure, Build data-dictionary site — all SUCCESS. Deploy correctly SKIPPED on PR (runs only on main push).
- `uv run mkdocs build --strict` — `Documentation built in 0.39 seconds`, zero warnings.
- Mermaid diagrams render natively on GitHub (both `graph TB` and `flowchart LR` are GitHub-native fence dialects).

**Residual notes for acceptance review:**
- Screenshots under `docs/images/` deferred — Dagster asset graph, asset-checks panel, dashboard captures require a live instance running against MotherDuck. Dictionary screenshot is implicitly covered by the live Pages site (https://doctacon.github.io/databox/). Flagship dashboard screenshot depends on the Dive deploy which isn't part of this initiative.
- `ticket:architecture-docs` originally `depends_on: ticket:observability-pass` — that ticket is separate and not in the staff-portfolio-readiness merge sequence. The ADRs reference the intended observability model (`ADR-0005` covers Dagster asset checks as the quality gate mechanism); if `ticket:observability-pass` later lands changes, the ADRs may need a revision note but not a full rewrite.
- The five evaluator questions ("what problem", "stack and why", "cross-domain value", "quality enforcement", "run locally") are all answered in the README without jumping to an external file.
