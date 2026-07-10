Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-fix-adk-runner-telemetry-cleanup.md

# ADK runner telemetry cleanup

## What was observed

A successful local trip-plan POST returned `201 Created` and persisted the plan, then Google ADK 2.4.0/OpenTelemetry 1.41.0 logged an app-name warning and three `Failed to detach context` tracebacks containing `GeneratorExit`.

The application returned from inside `async for event in runner.run_async(...)` at the first `TripPlanResult`. That abandoned ADK's nested traced async generators at a yield point. Deferred async-generator finalization ran cleanup from a different `contextvars.Context`, so OpenTelemetry could not reset its tokens. The three errors corresponded to nested ADK tracing scopes. Independently, ADK inferred app namespace `agents` from the root agent module directory while the runner/session used `databox_birding_trip_planner`.

## Procedure and result

`run_trip_planner_agent_async` now retains the first `TripPlanResult`, consumes the real ADK runner generator to normal exhaustion, raises the unchanged error if no result exists, and returns only after cleanup. Runner and session share ADK's inferred `agents` namespace.

The regression wraps the installed `InMemoryRunner.run_async` only to observe exhaustion, executes the complete scenario with `asyncio.run`, and inspects captured logs only after Python 3.12 has run `shutdown_asyncgens()` and closed the loop.

A temporary adversarial old-shape comparison restored early return while retaining the corrected namespace. After loop shutdown it produced a successful result, `exhausted=False`, exactly three `Failed to detach context` records, and three `GeneratorExit` traces. The current implementation reports `exhausted=True` with none of those records or the app-name warning.

## Validation

```text
uv run --no-sync pytest tests/test_birding_trip_planner.py -q
12 passed.

uv run --no-sync pytest tests/test_cloudflare_workers_ai.py tests/test_birding_trip_planner.py tests/test_api.py --no-cov -q
48 passed.

uv run --no-sync ruff check packages/databox/databox/agents/birding_trip_planner.py tests/test_birding_trip_planner.py
Passed.

uv run --no-sync mypy packages/databox/databox/agents/birding_trip_planner.py
Passed.

pre-commit and git diff checks
Passed; no staged files.
```

The API suite includes a real successful POST, 201 assertion, persisted tool evidence, list, and identical detail reload.

## What this supports

- The observed traces were non-fatal ADK telemetry cleanup errors, not Cloudflare/model/media/planner failures.
- The runner now reaches normal exhaustion before returning the persisted result.
- Existing output, persistence, model, media, retry, timeout, fallback, and API contracts remain unchanged.
- No runtime logger suppression, monkeypatch, dependency patch, or package restructure was introduced.

## Limits

The currently running Uvicorn process must be restarted to load this code. Validation used deterministic local planner/API tests rather than another live Cloudflare request.
