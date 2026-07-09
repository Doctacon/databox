Status: done
Created: 2026-07-08
Updated: 2026-07-09

# Build Birding Trip Copilot

## Scope

Parent plan for the first agentic birding application in Databox.

The aggregate goal was to deliver a Python/Google ADK trip-planning agent that uses Databox warehouse data plus GBIF, Xeno-canto, and Open-Meteo context, persists its plan/evidence/tool trace, evaluates the agent with DeepEval, and presents the result through a MotherDuck Dive.

This parent ticket is a plan and was not implemented directly; child tickets owned executable work.

## Governing specs and research

- `.10x/specs/birding-trip-copilot.md`
- `.10x/specs/birding-agent-data-integrations.md`
- `.10x/specs/birding-trip-plan-dive.md`
- `.10x/specs/birding-agent-evaluations.md`
- `.10x/research/2026-07-08-birding-agent-system-shaping.md`
- `docs/new-source.md`
- `docs/adr/0001-duckdb-as-primary-warehouse.md`
- `docs/adr/0005-dagster-as-sole-orchestrator.md`
- `docs/adr/0007-quack-single-file-local-ingest.md`

## Child tickets

1. `.10x/tickets/done/2026-07-08-add-gbif-source-pipeline.md`
2. `.10x/tickets/done/2026-07-08-add-xeno-canto-source-pipeline.md`
3. `.10x/tickets/done/2026-07-08-add-open-meteo-trip-context-tool.md`
4. `.10x/tickets/done/2026-07-08-model-birding-planner-sql-interfaces.md`
5. `.10x/tickets/done/2026-07-08-implement-adk-trip-planner-persistence.md`
6. `.10x/tickets/done/2026-07-08-add-birding-agent-deepeval-suite.md`
7. `.10x/tickets/done/2026-07-08-build-trip-plan-motherduck-dive.md`

## Sequencing

Completed in dependency order:

- GBIF and Xeno-canto source pipelines.
- Open-Meteo request-time trip context tool.
- Planner-ready SQL interfaces and persistence tables.
- ADK trip-planner runtime and persistence.
- DeepEval suite.
- MotherDuck Dive-as-code artifact.

## Aggregate acceptance criteria

- New source/tool integrations satisfy `.10x/specs/birding-agent-data-integrations.md`: satisfied by child evidence for GBIF, Xeno-canto, Open-Meteo, and planner SQL interfaces.
- Trip planner behavior satisfies `.10x/specs/birding-trip-copilot.md`: satisfied by ADK runtime/persistence tests, DeepEval scenarios, and aggregate validation.
- DeepEval suite satisfies `.10x/specs/birding-agent-evaluations.md`: satisfied by `task eval:agent` with 2 passing deterministic scenarios.
- MotherDuck Dive satisfies `.10x/specs/birding-trip-plan-dive.md`: satisfied by Dive SQL contract test and local Vite build.
- `task ci` passes after all code tickets are complete: satisfied, `145 passed`.
- A full local run can produce at least one persisted trip plan that the Dive can query: satisfied by ADK planner tests and Dive SQL contract test over the persisted artifact shape.
- Evidence records map each child ticket's acceptance criteria to observed results: satisfied by child evidence and `.10x/evidence/2026-07-09-birding-trip-copilot-aggregate-validation.md`.

## Progress and notes

- 2026-07-08: User ratified MVP choices: trip planner only, GBIF + Xeno-canto + Open-Meteo data slice, no life list, MotherDuck Dive over persisted plans, DeepEval in first slice.
- 2026-07-08: Created active specs and child ticket plan.
- 2026-07-09: Completed all seven child tickets.
- 2026-07-09: Fixed CI dependency incompatibility introduced by DeepEval by pinning `aiohttp<3.14` for vcrpy/pytest-recording compatibility.
- 2026-07-09: Review found two correctness issues: ADK was initially descriptor-only and Dive trace status used `success` instead of persisted `ok`. Both were fixed.
- 2026-07-09: Follow-up review passed. Aggregate validation passed: `task ci`, `task eval:agent`, `task docs:build`, and `.dive-preview` Vite build.

## Evidence and review

- `.10x/evidence/2026-07-08-gbif-source-pipeline.md`
- `.10x/evidence/2026-07-08-xeno-canto-source-pipeline.md`
- `.10x/evidence/2026-07-08-open-meteo-trip-context-tool.md`
- `.10x/evidence/2026-07-08-birding-planner-sql-interfaces.md`
- `.10x/evidence/2026-07-09-adk-trip-planner-persistence.md`
- `.10x/evidence/2026-07-09-birding-agent-deepeval-suite.md`
- `.10x/evidence/2026-07-09-trip-plan-motherduck-dive.md`
- `.10x/evidence/2026-07-09-birding-trip-copilot-aggregate-validation.md`
- `.10x/reviews/2026-07-09-birding-trip-copilot-review.md`

## Blockers

None.

## Residual risk

- Live Xeno-canto ingestion requires a valid `XENO_CANTO_API_KEY`; a live full refresh was not run in this session.
- The ADK execution path is a deterministic custom `BaseAgent` through `InMemoryRunner`, not an LLM-backed orchestration session.
- The Dive was implemented and built locally as Dives-as-code; it was not saved to a live MotherDuck workspace in this session.
