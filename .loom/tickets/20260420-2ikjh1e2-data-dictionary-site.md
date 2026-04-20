---
id: ticket:data-dictionary-site
kind: ticket
status: ready
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 2
---

# Goal

Generate a static data-dictionary + column-level lineage site from SQLMesh model metadata and Soda contracts. Publish via GitHub Pages so a recruiter can browse tables, columns, descriptions, tests, and upstream/downstream lineage without cloning the repo.

# Why

Data discoverability is a staff-level problem. Showing that a one-operator platform still has a queryable catalog — auto-generated from the same artifacts used at runtime — tells a hiring manager that governance is automated, not manual.

# In Scope

- A `scripts/generate_docs.py` that:
  - walks SQLMesh models in `transforms/main/models/` via the SQLMesh Python API
  - reads Soda contracts from `soda/contracts/`
  - emits Markdown or MkDocs-Material pages per model with: description, columns + types + descriptions, contracts in effect, upstream/downstream models, example `SELECT`
  - emits a global lineage page rendered with Mermaid from SQLMesh's lineage graph
- MkDocs config (`mkdocs.yml`) using MkDocs-Material (Apache 2.0)
- GitHub Actions workflow `.github/workflows/docs.yaml` that builds on `main` and deploys to `gh-pages`
- Landing page that links to the case-study README (see ticket:architecture-docs)

# Out of Scope

- Interactive SQL query interface (Dive handles exploration)
- Usage-stats dashboards
- Editing docs by hand — everything must be generated
- Column-level lineage beyond what SQLMesh already exposes

# Acceptance Criteria

- `uv run python scripts/generate_docs.py` regenerates the full site locally in under 30 seconds
- Every SQLMesh model appears with its columns, types, and any Soda checks
- Lineage page renders and each node links to its model page
- `docs.yaml` workflow deploys to GitHub Pages on every `main` push
- Published URL is linked from root README
- Regenerating after adding a new model reflects it without manual edits

# Approach Notes

- Prefer MkDocs-Material over Docusaurus to keep tooling in Python
- SQLMesh exposes `context.models` and `context.dag` — use those, don't re-parse SQL
- Soda contract parser already exists in Soda Core; use its data model rather than YAML spelunking
- Keep the generator side-effect-free: idempotent, deterministic ordering for clean git diffs when checked in

# Evidence Expectations

- Published Pages URL
- Screenshots of a model page and the lineage page in the case-study README
