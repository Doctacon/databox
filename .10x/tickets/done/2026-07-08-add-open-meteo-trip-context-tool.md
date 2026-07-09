Status: done
Created: 2026-07-08
Updated: 2026-07-08
Parent: .10x/tickets/done/2026-07-08-build-birding-trip-copilot.md
Depends-On: None

# Add Open-Meteo trip context tool

## Scope

Add the first Open-Meteo weather/elevation integration for request-time Birding Trip Copilot context.

Per `.10x/specs/birding-agent-data-integrations.md`, Open-Meteo is an agent tool in the MVP rather than a scheduled dlt pipeline because trip plans use dynamic user-selected locations and future windows.

In scope:

- Add a Python tool/module that retrieves forecast/weather and elevation context for a requested coordinate/time window.
- Define the returned context shape consumed by the planner.
- Define and implement how used Open-Meteo responses are persisted as trip-plan evidence.
- Add deterministic tests with mocked Open-Meteo responses.
- Document API limitations, units, and unavailable-data behavior.

Out of scope:

- Scheduled Open-Meteo dlt pipeline.
- Long-term weather cache/history modeling beyond persisted trip-plan evidence.
- Planner prompt/agent implementation.
- Dive implementation.

## Acceptance criteria

- A tool can retrieve weather/elevation context for a given latitude/longitude and outing window.
- The tool returns normalized units and enough metadata/provenance for downstream evidence.
- The tool handles unavailable/error responses without crashing the planner contract.
- Used responses can be persisted as trip-plan evidence artifacts.
- Tests cover success, unavailable/error, and unit/field normalization behavior with mocked responses.

## Evidence expectations

Record evidence with:

- tests executed,
- example normalized tool output,
- persistence target/shape,
- limitations of the selected Open-Meteo endpoints.

## Progress and notes

- 2026-07-08: Ticket opened from parent Birding Trip Copilot plan.
- 2026-07-08: Added `databox.agent_tools.open_meteo` request-time Open-Meteo forecast/elevation tool with normalized `OpenMeteoTripContext` output.
- 2026-07-08: Added `persist_open_meteo_evidence(...)`, which stores the used context as one `birding_agent.trip_plan_evidence` row with summary/payload/caveats JSON for trip-plan reproducibility.
- 2026-07-08: Added deterministic mocked tests for success, unavailable API responses, empty-window partial responses, normalization, and DuckDB persistence.
- 2026-07-08: Verified focused pytest, ruff, format check, and mypy. See `.10x/evidence/2026-07-08-open-meteo-trip-context-tool.md`.

## Blockers

None.
