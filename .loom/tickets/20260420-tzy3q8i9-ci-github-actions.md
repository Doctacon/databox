---
id: ticket:ci-github-actions
kind: ticket
status: ready
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 1
---

# Goal

Stand up GitHub Actions CI that runs on every push and PR to `main`, enforcing lint, typecheck, SQLMesh plan validation, Soda contract validation, and Python tests. Failure blocks merge.

# Why

No CI exists today. A recruiter will check the GitHub Actions tab and the README for a green build badge within the first thirty seconds. More importantly, every other ticket in this initiative assumes CI is the enforcement surface for contracts, tests, and quality gates.

# In Scope

- `.github/workflows/ci.yaml` with jobs:
  - `lint`: `ruff check` + `ruff format --check` across `packages/`
  - `typecheck`: `mypy` or `pyright` across `packages/`
  - `python-tests`: `uv run pytest` across `packages/`
  - `sqlmesh-plan`: `sqlmesh plan --no-auto-apply` against a fresh local DuckDB in `transforms/main/`
  - `soda-validate`: `soda contract verify` (schema-only, no data scan) across `soda/contracts/`
- `uv sync` with caching keyed on `uv.lock`
- Pre-commit config integration (`pre-commit run --all-files` as a job or as part of lint)
- README badge pointing at the workflow
- `workflow_dispatch` trigger for manual re-runs

# Out of Scope

- Deploy/publish workflows
- Running full `soda scan` against live data in CI (only contract/schema validation)
- MotherDuck backend in CI (local DuckDB is enough)
- Release automation

# Acceptance Criteria

- Opening a PR triggers all jobs; all pass on `main` at the moment of ticket close
- Introducing a lint error, type error, failing test, invalid SQLMesh model, or malformed Soda contract breaks CI in a local test branch and is verified via evidence
- `uv sync` step reuses cache between runs (verified in second run logs)
- README shows the green build badge
- Workflow file lives at `.github/workflows/ci.yaml` and is reviewed against the GitHub Actions `pin-to-sha` posture for third-party actions

# Approach Notes

- Use `actions/checkout@<sha>`, `astral-sh/setup-uv@<sha>`, pinned by commit SHA per supply-chain hygiene
- For SQLMesh plan, seed a throwaway DuckDB file under `/tmp`; do not commit sample data
- If `mypy` surfaces too many pre-existing errors, open a follow-up ticket rather than silencing — record it as evidence
- Matrix over Python versions only if `.python-version` changes; single version is fine for now

# Evidence Expectations

- Link to a passing workflow run on `main`
- Link to a deliberately-failing branch showing each gate can fail
