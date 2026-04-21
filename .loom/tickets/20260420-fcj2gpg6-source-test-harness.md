---
id: ticket:source-test-harness
kind: ticket
status: closed
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-21T19:20:00Z
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

# Work Log

## Iter 1 — 2026-04-20

Landed 9 tests (3 sources × {unit, schema, smoke}) with recorded VCR cassettes.

- **Packet**: `.loom/packets/20260420-m6wyjlln-source-test-harness.md` (inline execution; no subagent).
- **Files created**:
  - `packages/databox-sources/tests/conftest.py` — `vcr_config`, schema-normalizer, in-memory duckdb pipeline factory, dlt-telemetry kill-switch
  - `packages/databox-sources/tests/{ebird,noaa,usgs}/test_resources.py` — per-resource unit tests
  - `packages/databox-sources/tests/{ebird,noaa,usgs}/test_schema.py` — syrupy dlt-schema snapshots
  - `packages/databox-sources/tests/{ebird,noaa,usgs}/test_smoke.py` — `pipeline.run(source)` into `:memory:` duckdb
  - `packages/databox-sources/README.md` — test-harness docs + re-record flow
  - `.loom/evidence/20260420-schema-drift-proof.md` — deliberate-drift diff
- **Files edited**:
  - `pyproject.toml` — added `pytest-recording>=0.13`, `syrupy>=4.0`; extended `testpaths` to include `packages`
  - `.github/workflows/ci.yaml` — removed pytest exit-5 tolerance; `tests` job now hard-fails on zero collected
- **Cassette scope**:
  - ebird (US-DC, days_back=1, max_results=50): 4 of 6 resources via `.with_resources(...)`; taxonomy excluded (~5MB response).
  - noaa (FIPS:11, TMAX, days_back=7) with `@pytest.mark.time_machine("2026-02-15T00:00:00Z")` because the source derives date range from `pendulum.now()`.
  - usgs (state_cd=RI, parameter_cd=00060, days_back=3) with same frozen clock.
- **Cassette sizes**: ebird 152K, noaa 28K, usgs 224K (total 404K — above the packet's 100K budget; ebird hotspots + usgs all-RI-sites dominate. Acceptable for a one-time tradeoff; noted in residual risks).
- **Secret scan**: EBIRD_API_TOKEN, NOAA_API_TOKEN, MOTHERDUCK_TOKEN all grep-clean against cassettes. `vcr_config` redacts headers + query params; `_scrub_response_body` hook strips token echoes from response bodies as belt-and-suspenders.
- **Telemetry**: dlthub telemetry disabled in tests via `RUNTIME__DLTHUB_TELEMETRY=false` + VCR `ignore_hosts=["telemetry.scalevector.ai"]`.
- **Deviations**:
  - Not all 6 ebird resources covered in smoke — `taxonomy` + `region_stats` omitted. Taxonomy cassette size is the blocker; region_stats is per-day and would multiply cassette size. Documented in README.
  - Support helper lives in `conftest.py` rather than a standalone `support.py` — `tests.support` import path was fragile from project-root pytest invocation. Collapsing into conftest was simpler than adding sys.path munging.
- **Result**: `uv run pytest packages/databox-sources/ --record-mode=none` → `9 passed in 2.84s`.

## Residual risks / follow-ups

- Cassette size budget exceeded (404K vs 100K target). Revisit if monorepo churns regularly.
- Taxonomy + region_stats resources untested. Consider a separate nightly sensor test (per ticket's "Out of Scope") or a dedicated tiny-fixture test.
- Frozen clock in NOAA/USGS tests hides real time-zone / DST issues in date math. Fine for a schema-stability floor; flag if timezone bugs surface.
- PR + CI verification pending.

## Recommended next state

`review_required` → push branch, open PR, confirm green CI, then `complete_pending_acceptance`.
