---
id: ticket:source-test-harness
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

Establish a test harness for `databox-sources` that runs in CI without live API calls. Every existing dlt source (eBird, NOAA, USGS) gets at least one unit test against a recorded fixture and one end-to-end smoke test that loads into an in-memory DuckDB.

# Why

dlt sources are the thinnest, most change-prone code in the repo — API schemas drift, auth headers break, pagination regresses. Today there is no way to catch these before production runs. Tests here are the highest-ROI reliability work in the project.

# In Scope

- `tests/` directory inside `packages/databox-sources/` (or sibling `tests/` per package per pytest convention)
- Shared fixtures: recorded HTTP responses via `pytest-recording` / `vcrpy` or simple JSON snapshots under `tests/fixtures/<source>/`
- Per source, at minimum:
  - unit test: resource function produces expected rows against a fixture response
  - schema test: generated dlt schema matches a checked-in snapshot (breaks loudly on drift)
  - smoke test: `dlt.pipeline(...).run(source)` against `duckdb(":memory:")` loads without error
- `pyproject.toml` test deps declared under `[dependency-groups]` (uv convention)
- Documentation snippet in `packages/databox-sources/README.md` for "how to re-record fixtures"

# Out of Scope

- Live-API smoke tests (those belong in a scheduled nightly Dagster sensor, not CI)
- Performance/load tests
- Testing the MotherDuck destination specifically (DuckDB memory is sufficient proxy)
- Full coverage of edge cases — goal is a durable floor, not 100% coverage

# Acceptance Criteria

- `uv run pytest packages/databox-sources` passes locally and in CI
- Each of `ebird`, `noaa`, `usgs` has ≥1 unit test, ≥1 schema-snapshot test, ≥1 in-memory load test
- Introducing a breaking change to a resource schema fails the snapshot test with a clear diff
- Fixture re-recording is documented and works with a single command
- CI `python-tests` job from `ticket:ci-github-actions` runs these tests

# Approach Notes

- Prefer `pytest-recording` (VCR cassettes) over hand-rolled JSON snapshots for API response fixtures — less maintenance
- Schema snapshots: serialize `pipeline.default_schema.to_pretty_yaml()` and diff
- Redact API keys from recorded cassettes (`filter_headers=['authorization', 'x-api-key']`)
- Use `tmp_path` fixtures to keep each test's DuckDB isolated

# Evidence Expectations

- Link to PR introducing the tests and passing CI run
- Screenshot or paste of a deliberate schema-drift failure showing the clear diff
