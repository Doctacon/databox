---
id: ticket:path-based-ci
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T19:30:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 1
depends_on:
  - ticket:source-layout-convention
---

# Goal

Only run CI jobs relevant to the files a PR changes. Full-matrix CI still runs on every merge to `main` and on any change to CI config itself, so regressions cannot hide.

# Why

Today every PR — including docs-only edits and single-source additions — runs the full matrix (Ruff, mypy, pytest, SQLMesh lint, schema-contract gate, Soda contract structure, MkDocs build). At 3 sources this costs ~4 minutes. At 20 sources with source-specific tests and per-source SQLMesh models, it will cost much more. A forker will feel it on every iteration.

Path-based triggers concentrate cost where it matters: a docs PR runs docs checks, a source-specific PR runs that source's tests, and everything still runs on `main` merges and CI-config changes.

# In Scope

- Introduce `paths:` filters on each CI job in `.github/workflows/ci.yaml` (and `docs.yaml`), following GitHub's documented path-filter syntax
- Path groups:
  - **docs-only**: `docs/**`, `*.md`, `mkdocs.yml` — runs MkDocs strict + link checks only
  - **loom-only**: `.loom/**` — runs loom record lint (if any) only
  - **source-<name>**: `packages/databox-sources/databox_sources/<name>/**`, `transforms/main/models/<name>/**`, `soda/contracts/<name>*/**` — runs source-specific tests + SQLMesh lint on that model subset + Soda contract validation for that source
  - **cross-cutting**: anything under `packages/databox/**`, `scripts/**`, root config — runs full matrix
  - **ci-config**: `.github/workflows/**` — runs full matrix
- On pushes to `main` (post-merge): full matrix always
- On release-branch pushes: full matrix always
- Job-dependency graph keeps the `schema-contract-gate` as a required status check regardless (it is cheap once SQLMesh plan runs)
- Document the routing in `docs/ci.md`

# Out of Scope

- Switching off GitHub Actions to a different runner (CircleCI, Buildkite, self-hosted)
- Speeding up individual jobs (caching optimisations are a separate concern)
- Concurrency-group tuning (separate PR if needed)

# Acceptance Criteria

- A docs-only PR triggers exactly one job: MkDocs strict + link check; full run completes in under 60 seconds
- A source-specific PR (only `packages/databox-sources/databox_sources/ebird/*` changes) triggers only the ebird test suite and cross-cutting gate, not NOAA/USGS tests
- A cross-cutting PR (e.g. touches `databox.config`) still triggers the full matrix
- A PR that changes `.github/workflows/ci.yaml` triggers the full matrix regardless of other paths
- `docs/ci.md` explains the routing and is linked from the CI workflow file as a comment
- Branch protection rules keep `schema-contract-gate` and `source-layout-lint` as required checks

# Approach Notes

- GitHub Actions path filters can be declared per job via `jobs.<id>.if: contains(github.event.pull_request.changed_files, 'docs/')` — use the cleaner `paths:` filter at the workflow trigger level where possible, and per-job `if:` where workflow-level filtering is too coarse
- `dorny/paths-filter` action gives a first-class conditional-path API if the built-in support gets awkward; open-source, stable
- Required status checks in branch protection must exist even when they are skipped — skipped-as-passed is fine in GitHub Actions
- Keep the "full matrix on main" invariant strict; any path routing bug should be caught by the post-merge run

# Evidence Expectations

- Three PRs with different change shapes, each showing the expected subset of jobs firing
- A `main` merge showing full matrix ran
- `docs/ci.md` rendered in deployed docs site

# Close Notes

Verified on main 2026-04-21: `.github/workflows/ci.yaml` uses `dorny/paths-filter` with per-path job routing, `docs/ci.md` published. Deliverable landed during earlier scaffold-polish work; ledger reconciled during status audit.
