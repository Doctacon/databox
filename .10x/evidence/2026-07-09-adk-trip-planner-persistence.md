Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-08-implement-adk-trip-planner-persistence.md

# Evidence: ADK trip planner runtime and persistence

## What was observed

The Birding Trip Copilot Python runtime was implemented with a Google ADK root-agent contract, deterministic bounded planner tools, DuckDB persistence, a local runnable module entrypoint, and focused tests. A later review fix changed the executed CLI/high-level trip-planning path to run through a minimal Google ADK `BaseAgent` via `InMemoryRunner`, while preserving deterministic bounded-tool behavior and avoiding LLM credentials.

## Procedure and results

1. Added `google-adk>=2.4.0` to `packages/databox/pyproject.toml` and refreshed `uv.lock` with `uv add --package databox google-adk`.

2. Added first-party agent runtime files:

   - `packages/databox/databox/agents/__init__.py`
   - `packages/databox/databox/agents/birding_trip_planner.py`

3. Implemented a deterministic `BirdingTripPlanner` workflow with these bounded tool steps:

   - `normalize_location`
   - `lookup_recent_observation_evidence`
   - `lookup_gbif_occurrence_evidence`
   - `fetch_open_meteo_trip_context`
   - `rank_likely_species`
   - `lookup_xeno_canto_media_evidence`
   - `build_trip_plan_evidence`
   - `persist_trip_plan`

4. Implemented `build_root_agent()` using `google.adk.agents.Agent` with the same bounded tool contract for future ADK orchestration/evaluation.

5. Review-fix amendment: implemented `BirdingTripPlannerAdkAgent`, a minimal `google.adk.agents.BaseAgent`, and routed the high-level `plan_trip(...)`/CLI path through `google.adk.runners.InMemoryRunner`. The deterministic `BirdingTripPlanner` remains the bounded-tool implementation used by that ADK agent.

6. Added local runnable entrypoint:

   ```bash
   python -m databox.agents.birding_trip_planner \
     --database-path <duckdb-file> \
     --location "Thumb Butte" \
     --start-at "2026-07-09T06:00:00" \
     --duration-minutes 90 \
     --trip-plan-id trip-cli-test \
     --mock-open-meteo
   ```

   This path is covered by `tests/test_birding_trip_planner.py::test_cli_generates_sample_plan_against_duckdb_file`, which seeds a temporary DuckDB file, invokes the module entrypoint, and verifies persisted rows.

7. Added deterministic tests in `tests/test_birding_trip_planner.py` covering:

   - ADK root-agent tool contract,
   - executed ADK runtime path through `run_trip_planner_agent(...)`,
   - trip plan generation from seeded planner views,
   - persisted `trip_plans`, `trip_plan_recommendations`, `trip_plan_evidence`, and `trip_plan_tool_traces`,
   - source-unavailable caveats when planner evidence views are absent,
   - local CLI/module entrypoint persistence.

8. Validation commands:

   ```bash
   .venv/bin/python -m pytest --no-cov tests/test_birding_trip_planner.py tests/test_open_meteo_tool.py -q
   ```

   Result: `9 passed, 4 warnings`.

   ```bash
   .venv/bin/ruff check packages/databox/databox/agents tests/test_birding_trip_planner.py
   .venv/bin/ruff format --check packages/databox/databox/agents tests/test_birding_trip_planner.py
   .venv/bin/mypy packages/databox/databox/agents tests/test_birding_trip_planner.py
   ```

   Results: ruff passed, format check passed, mypy passed.

   ```bash
   .venv/bin/dg check defs --use-active-venv
   ```

   Result: `All definitions loaded successfully.`

## What this supports

- A local command/module path can generate a supported-location trip plan without the Dive.
- The planner uses bounded deterministic tools and records eight tool traces per run.
- The planner persists queryable trip-plan artifacts for the MotherDuck Dive contract.
- The planner does not use or assume personal life-list/history data.
- The planner records source-unavailable caveats when evidence views/sources are sparse or absent.

## Limits

- The local tests use deterministic seeded DuckDB tables and mocked Open-Meteo responses; live API calls were not made in this ticket.
- The executed runtime now runs through Google ADK's local `InMemoryRunner`, but it remains a deterministic custom `BaseAgent` path and does not run an LLM-backed ADK session. This preserves local/test determinism and avoids model credentials.
- The ranking logic is intentionally simple and deterministic for the first MVP slice; DeepEval and future tuning are owned by follow-up tickets.
