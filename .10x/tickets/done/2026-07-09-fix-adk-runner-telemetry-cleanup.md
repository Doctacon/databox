Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: None
Depends-On: None

# Fix ADK runner telemetry cleanup

## Scope

Remove the non-fatal Google ADK/OpenTelemetry cleanup errors and app-name warning observed after a successful local trip-plan request.

The executed path in `packages/databox/databox/agents/birding_trip_planner.py` currently returns from inside `async for event in runner.run_async(...)` as soon as it sees `TripPlanResult`. That abandons ADK's nested async-generator chain at a yield point. Python later injects `GeneratorExit`; OpenTelemetry 1.41.0 attempts to detach context tokens from a different `contextvars.Context`, logs three `Failed to detach context` errors, and skips the remainder of ADK's normal generator completion path.

Separately, Google ADK 2.4.0 infers the root app name as `agents` from the module directory but the runner/session are named `databox_birding_trip_planner`, producing the independent app-name warning.

## Required work

- Retain the first `TripPlanResult` while consuming `runner.run_async(...)` to normal completion, then return it after the loop.
- Preserve the existing error when no result is produced.
- Align the runner/session app namespace with the ADK origin contract without suppressing the warning or patching installed dependencies.
- Add a regression test that exercises the real async-generator lifecycle and proves successful output with no app-name warning, `GeneratorExit` telemetry traceback, or `Failed to detach context` log.
- Preserve planner output, persistence, strict Cloudflare behavior, request latency bounds, and FastAPI response contracts.

## Acceptance criteria

- A successful POST still returns 201 and persists/reloads the plan.
- The ADK event generator reaches normal exhaustion before `run_trip_planner_agent_async` returns.
- Server logs contain no app-name mismatch warning and no OpenTelemetry detach error.
- Provider, planner, API, and focused regression tests pass.
- No telemetry logger suppression, monkeypatch, dependency fork, fallback, retry, or timeout change is introduced.

## Explicit exclusions

- No replacement of Google ADK or OpenTelemetry.
- No change to trip-planning semantics or media discovery.
- No broad package restructuring solely to silence a heuristic warning.

## Evidence and references

- Runtime observation: POST returned `201 Created`, followed by three OpenTelemetry context-detach tracebacks caused by `GeneratorExit`.
- Installed versions: `google-adk==2.4.0`, `opentelemetry-api==1.41.0`, `opentelemetry-sdk==1.41.0`.
- Upstream reproduction: https://github.com/google/adk-python/issues/4894
- Upstream attempted fix, closed unmerged: https://github.com/google/adk-python/pull/4919
- Relevant source: `run_trip_planner_agent_async` in `packages/databox/databox/agents/birding_trip_planner.py`; ADK `Runner.run_async`, `BaseAgent.run_async`, and telemetry context managers.

## Progress and notes

- 2026-07-09: Root cause established from the runtime trace, local source, installed ADK/OpenTelemetry source, and upstream reproduction. The successful plan result is already persisted before cleanup fails; this is internal lifecycle/telemetry noise rather than a failed trip plan.
- 2026-07-09: Aligned the runner and session namespace to ADK's inferred `agents` origin. `run_trip_planner_agent_async` now retains the first `TripPlanResult`, drains the real runner async generator to normal exhaustion, preserves the existing no-result error, and returns only after cleanup completes.
- 2026-07-09: Added a real-runner lifecycle/log regression that wraps the installed ADK runner only as a test completion probe, verifies normal exhaustion and successful output, and asserts no app-name mismatch, `Failed to detach context`, or `GeneratorExit` log. No runtime suppression, monkeypatch, dependency change, retry, timeout, or package restructure was introduced.
- 2026-07-09: Review found the async pytest shape asserted logs before deferred async-generator finalization was guaranteed. Converted the regression to a synchronous test whose real scenario runs inside `asyncio.run`; log assertions occur only after `shutdown_asyncgens` and loop closure. Removed obsolete GC/sleep mechanics.
- 2026-07-09: A temporary old-shape comparison retained the fixed `agents` namespace but restored the early return. The regression failed as intended and captured exactly three delayed OpenTelemetry `Failed to detach context` errors with three `GeneratorExit` tracebacks after loop shutdown; the implementation file was restored before final validation.
- 2026-07-09: Focused Ruff, formatting, MyPy, 12 planner tests, and 48 provider/planner/API tests passed.
- 2026-07-09: Final independent review passed lifecycle exhaustion, deferred-finalization regression, namespace alignment, unchanged behavior, and API persistence/reload criteria. Evidence: `.10x/evidence/2026-07-09-adk-runner-telemetry-cleanup.md`. Review: `.10x/reviews/2026-07-09-adk-runner-telemetry-cleanup-review.md`.
- 2026-07-09: Retrospective: async-generator results do not imply invocation completion. Callers that need ADK's final output MUST drain the generator so callbacks, plugins, compaction, and telemetry clean up in the creating context. Regression checks for deferred cleanup must inspect logs only after `shutdown_asyncgens()`/loop closure. This focused test captures the reusable invariant; no separate knowledge or skill record is needed.

## Blockers

None.
