Status: done
Created: 2026-07-08
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-08-build-birding-trip-copilot.md
Depends-On: .10x/tickets/2026-07-08-model-birding-planner-sql-interfaces.md

# Implement ADK trip planner and persistence

## Scope

Implement the Python/Google ADK Birding Trip Copilot workflow and persist its outputs for the MotherDuck Dive.

In scope:

- Add a first-party Python package/module layout for the agent runtime.
- Add Google ADK dependency/configuration in the appropriate project dependency group.
- Implement bounded planner tools for location normalization, observation/context lookup, Open-Meteo context, media lookup, ranking, and persistence.
- Implement the root trip planner agent using the active specs.
- Persist trip plan, recommended species, evidence, and tool-trace artifacts into the SQL interfaces defined by `.10x/tickets/2026-07-08-model-birding-planner-sql-interfaces.md`.
- Provide a local runnable entrypoint for generating at least one trip plan without the Dive.
- Add unit tests for deterministic tool behavior and persistence.

Out of scope:

- New dlt source work.
- DeepEval suite wiring.
- MotherDuck Dive implementation.
- Separate species plausibility, field ID, or coaching user-facing workflows.

## Acceptance criteria

- A local command or script can generate a trip plan for a supported location/time window.
- The planner uses bounded tools and records tool traces.
- The planner persists a queryable trip-plan artifact with recommendations and evidence.
- The planner does not use or assume personal life-list/history data.
- The final plan includes evidence/provenance caveats when sources are sparse or unavailable.
- Targeted tests for tool behavior and persistence pass.

## Evidence expectations

Record evidence with:

- command used to generate a sample plan,
- resulting persisted row counts/table names,
- representative final output excerpt,
- tests executed,
- limitations or caveats discovered.

## Progress and notes

- 2026-07-08: Ticket opened from parent Birding Trip Copilot plan.
- 2026-07-09: Added `google-adk>=2.4.0`, first-party `databox.agents` module layout, deterministic `BirdingTripPlanner`, ADK root-agent tool contract, local runnable module entrypoint, trip-plan persistence, and focused tests.
- 2026-07-09: Validated with focused planner/Open-Meteo pytest, ruff, format check, mypy, and `dg check defs`. See `.10x/evidence/2026-07-09-adk-trip-planner-persistence.md`.
- 2026-07-09: Review fix: routed the executed high-level planner/CLI path through a minimal Google ADK `BaseAgent` via `InMemoryRunner` while preserving the deterministic bounded-tool planner and local tests.

## Blockers

None.
