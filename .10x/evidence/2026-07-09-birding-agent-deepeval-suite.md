Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-08-add-birding-agent-deepeval-suite.md, .10x/specs/birding-agent-evaluations.md

# Evidence: Birding Trip Copilot DeepEval suite

## What was observed

The first deterministic DeepEval suite for the Birding Trip Copilot was added and validated locally. The suite exercises the bounded-tool planner runtime without live external API calls, OpenAI/LLM calls, or secrets.

## Procedure and results

1. Added DeepEval as a scoped dev dependency:

   ```bash
   uv add --dev deepeval
   ```

   Result: `deepeval==4.0.7` added to the workspace dev dependency group and `uv.lock` refreshed.

2. Added `task eval:agent` to run the deterministic agent eval suite with local-safe env defaults:

   ```bash
   task eval:agent
   ```

   The target sets:

   - `CONFIDENT_OPEN_BROWSER=false`
   - `DEEPEVAL_CACHE_FOLDER=.cache/deepeval`
   - `DEEPEVAL_TELEMETRY_OPT_OUT=true`
   - `PYTEST_ADDOPTS=--no-cov`

3. Added DeepEval tests at `tests/evals/test_birding_trip_copilot_deepeval.py` with two deterministic scenarios:

   - `golden-thumb-butte-morning-trip-plan`
   - `sparse-location-source-unavailable-caveats`

4. Metrics used:

   - DeepEval `ToolCorrectnessMetric` with exact-match tool ordering against the planner's eight expected tool traces.
   - `PersistedEvidenceMetric`, a deterministic DeepEval `BaseMetric` checking persisted evidence/provenance sources.
   - `NoPersonalHistoryAssumptionMetric`, a deterministic DeepEval `BaseMetric` checking that output and rationales do not assume life-list/personal-history data.
   - `SourceUnavailableCaveatMetric`, a deterministic DeepEval `BaseMetric` checking missing source families are persisted and surfaced as caveats.

   A local no-op DeepEval model placeholder is passed to `ToolCorrectnessMetric` because DeepEval 4.0.7 initializes a model even when the metric is used only for exact local tool-call comparison. The no-op model is not called; the final eval reported `token cost: None`.

5. Final eval command:

   ```bash
   task eval:agent
   ```

   Result:

   ```text
   2 passed, 7 warnings in 2.37s
   Test Results (2 total tests):
      Pass Rate: 100.0% | Passed: 2 | Failed: 0
   token cost: None
   ```

6. Focused planner regression tests:

   ```bash
   .venv/bin/python -m pytest --no-cov tests/test_birding_trip_planner.py tests/test_open_meteo_tool.py -q
   ```

   Result:

   ```text
   9 passed, 4 warnings in 2.35s
   ```

7. Static checks for changed Python files:

   ```bash
   .venv/bin/ruff check tests/evals/test_birding_trip_copilot_deepeval.py packages/databox/databox/agents tests/test_birding_trip_planner.py
   .venv/bin/ruff format --check tests/evals/test_birding_trip_copilot_deepeval.py packages/databox/databox/agents tests/test_birding_trip_planner.py
   MYPYPATH=packages/databox:packages/databox-sources .venv/bin/mypy tests/evals/test_birding_trip_copilot_deepeval.py packages/databox/databox/agents tests/test_birding_trip_planner.py
   ```

   Results:

   ```text
   Ruff check: All checks passed.
   Ruff format: 4 files already formatted.
   Mypy: Success: no issues found in 4 source files.
   ```

8. CI repair after DeepEval introduced unpinned `aiohttp`:

   DeepEval 4.0.7 pulled `aiohttp 3.14.1`, which broke VCR-backed source tests during pytest-recording setup:

   ```text
   AttributeError: module 'aiohttp.streams' has no attribute 'AsyncStreamReaderMixin'
   ```

   The project uses `pytest-recording`/`vcrpy 8.1.1`; that VCR aiohttp stub path still expects `AsyncStreamReaderMixin`. Added a scoped workspace dev dependency pin:

   ```toml
   "aiohttp<3.14"
   ```

   Then refreshed `uv.lock` / `.venv`, resulting in:

   ```text
   aiohttp=3.13.5
   vcrpy=8.1.1
   has AsyncStreamReaderMixin=True
   ```

   Focused failing VCR-backed source tests now pass:

   ```bash
   .venv/bin/python -m pytest --no-cov packages/databox-sources/tests/ebird packages/databox-sources/tests/noaa packages/databox-sources/tests/usgs -q
   ```

   Result:

   ```text
   12 passed
   ```

   Full CI now passes:

   ```bash
   task ci
   ```

   Result:

   ```text
   145 passed, 35 warnings
   Staging SQL matches contracts.
   transforms/main/models/analytics/platform_health.sql matches source registry.
   ```

## What this supports

- A documented local command runs the DeepEval suite.
- The eval suite covers a golden Thumb Butte trip-planning scenario.
- The eval checks expected tool use rather than only final text.
- The eval checks persisted evidence/provenance behavior.
- The eval checks that the MVP does not assume personal life-list/history data.
- The eval suite is deterministic and uses seeded DuckDB data plus mocked Open-Meteo responses instead of live APIs.
- The eval suite explicitly covers source-unavailable caveat behavior.

## Limits

- DeepEval 4.0.7's built-in `ToolCorrectnessMetric` initializes an LLM model by default; this suite passes a no-op local model to keep exact-match tool checks local and deterministic.
- The suite does not run an LLM-backed ADK session. It evaluates the deterministic bounded-tool planner runtime and persisted traces, which is the implemented MVP execution path.
- DeepEval prints Confident AI promotional text after successful local runs; no login/API key was used and the final run reported `token cost: None`.
- The suite uses fixtures/mocks and does not validate live eBird, GBIF, Xeno-canto, or Open-Meteo service availability.
