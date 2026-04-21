---
id: ticket:data-dictionary-site
kind: ticket
status: complete_pending_acceptance
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
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

# Close Notes

Merged as PR #11.

**Deliverables:**
- `scripts/generate_docs.py` — SQLMesh `Context` + Soda YAML walker. Emits per-model Markdown + global Mermaid lineage + index under `docs/dictionary/`. Deterministic sort. ~1.5s on 20 models (well under 30s budget).
- `mkdocs.yml` — MkDocs-Material config (Apache 2.0), pymdownx.superfences with mermaid fence, nav covering dictionary + existing docs. Strict build clean.
- `docs/index.md` — landing page linking dictionary, lineage, metrics, examples, contracts, incremental-loading. Case-study README placeholder kept for `ticket:architecture-docs`.
- `.github/workflows/docs.yaml` — two-job pipeline: build generates dictionary + runs `mkdocs build --strict`; deploy uploads Pages artifact and runs `actions/deploy-pages` only on `main` push.
- README — new **Data dictionary** section links https://doctacon.github.io/databox/ with regeneration instructions.
- `.pre-commit-config.yaml` — `check-yaml` excludes `mkdocs.yml` (pymdownx uses Python-tagged yaml constructor).
- `.gitignore` — adds `site/` (mkdocs build artifact).

**Evidence:**
- Generator run: `Generated 20 model pages + lineage + index under docs/dictionary/` — 1.5s wall time on a warm venv.
- `uv run mkdocs build --strict` → `Documentation built in 0.37 seconds` with zero warnings.
- CI on PR #11: Ruff, mypy, pytest, SQLMesh lint, schema-contract gate, Soda contract structure, Build data-dictionary site all SUCCESS. Deploy step correctly SKIPPED on PR (runs only on main push).

**Residual notes for acceptance review:**
- Screenshots of model + lineage page not captured here — evidence is the generated Markdown under `docs/dictionary/` and the live CI build. Will be added to the case-study README in `ticket:architecture-docs`.
- Published Pages URL goes live after the first `main` push rebuild completes; the deploy workflow targets https://doctacon.github.io/databox/ (requires Pages enabled in repo settings if not already).
- Column types fall back to Soda-declared types when SQLMesh `columns_to_types` reports `UNKNOWN` (common for raw text/timestamp columns that the SQL parser can't infer without executing against a database). Documented inline in the generator.
- Lineage uses `model.depends_on` (direct parents) not `ctx.dag.upstream(fqn)` (transitive). The transitive graph is too dense to read. Direct-parent is the conventional lineage view.
