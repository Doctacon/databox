---
id: ticket:mypy-strict-gate
kind: ticket
status: ready
created_at: 2026-04-21T21:00:00Z
updated_at: 2026-04-21T21:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 5
depends_on: []
---

# Goal

Drop `mypy --ignore-missing-imports` as the default posture. New code in `packages/databox/**` and `packages/databox-sources/**` must pass mypy strict. Add a pytest coverage floor on those packages so regressions are visible in CI.

# Why

Today's `Taskfile.yaml` line 25: `mypy . --ignore-missing-imports`. That's the weakest possible mypy posture — errors originating in any third-party package with missing stubs are silenced, and the suppression bleeds into first-party code because `--ignore-missing-imports` is global. A staff-level reviewer scans the Taskfile in 30 seconds and sees that the type-checking claim in the README is soft. Similarly, there's no coverage floor: the test suite is 1811 LOC against 6985 LOC of source (~26%), but a regression that drops coverage to 10% would not fail CI.

# In Scope

- Configure per-package mypy strictness in `pyproject.toml`:
  - `packages/databox/databox/**` → strict (`disallow_untyped_defs`, `disallow_any_generics`, `no_implicit_optional`, `warn_unused_ignores`, `warn_redundant_casts`)
  - `packages/databox-sources/databox_sources/**` → strict (same settings)
  - Third-party without stubs → whitelisted via targeted `[[tool.mypy.overrides]]` blocks, NOT globally
  - Tests and scripts: current relaxed settings are fine for now
- Replace `mypy . --ignore-missing-imports` in the `ci` task with `mypy packages/` (relying on per-package config, no global suppression)
- Add coverage: `pyproject.toml` `[tool.coverage.run]` + `[tool.coverage.report]` with `fail_under = 70` targeting `packages/databox/databox/` + `packages/databox-sources/databox_sources/` (exclude tests, exclude `__init__.py`, exclude orchestration `definitions.py` since it's the top-level wiring)
- Update `ci` task: `pytest --cov --cov-report=term-missing`
- Add a coverage badge to the README (codecov or shields.io reading the coverage XML artifact) — optional if the coverage XML is published, but worth the 10 lines for portfolio signal
- Fix whatever type errors surface from the strictness flip — likely in `_factories.py` (the `client: t.Any` parameter, the `fetchone()` result unpacking in `analytics.py::mart_cost_summary`)

# Out of Scope

- `mypy --strict` repo-wide (too noisy for scripts and the `app/` Streamlit prototype)
- 90%+ coverage floor — 70% is the right first step; raise it once strict typing lands and the codebase rebaselines
- Adding pyright alongside mypy
- Runtime type enforcement (beyond the pydantic-source-typing already in place)

# Acceptance Criteria

- `mypy packages/` (no `--ignore-missing-imports`) passes cleanly against main
- `pytest --cov` run in CI has `--cov-fail-under=70` and passes
- `pyproject.toml` has explicit per-package mypy config
- A test intentionally added to drop coverage below 70% causes CI to fail; removing it restores green
- README badge shows live coverage

# Approach Notes

- Expect to write `# type: ignore[specific-code]` in a handful of places where third-party types genuinely cannot be narrowed — that's the correct outcome, not the bad one. The bad one is silent blanket ignores.
- Order of work:
  1. Add per-package overrides + whitelists in `pyproject.toml`
  2. Run `mypy packages/` locally, fix each error
  3. Flip the Taskfile
  4. Add coverage floor, fix any gaps
  5. Commit

# Evidence Expectations

- CI run with the stricter mypy invocation, green
- CI run with `--cov-fail-under=70`, green
- README badge live
