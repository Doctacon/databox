Status: done
Created: 2026-07-08
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-08-build-birding-trip-copilot.md
Depends-On: .10x/tickets/2026-07-08-implement-adk-trip-planner-persistence.md

# Add Birding Trip Copilot DeepEval suite

## Scope

Add the first DeepEval suite for the Birding Trip Copilot.

In scope:

- Add DeepEval dependency/configuration in a scoped project dependency group.
- Add at least one golden trip-planning scenario.
- Evaluate expected tool use, evidence/provenance behavior, and absence of personal-history assumptions.
- Prefer deterministic fixtures/mocks over live API calls.
- Document how to run the eval suite.

Out of scope:

- Full benchmark suite for every future agent.
- Live external API reliability tests.
- Separate user-facing species plausibility/field ID/coach evals.

## Acceptance criteria

- A documented command runs the DeepEval suite locally.
- At least one golden trip-planning scenario is covered.
- The eval checks expected tool use, not just answer text.
- The eval checks that the output or persisted artifacts include evidence/provenance.
- The eval checks that personal life-list/history is not assumed.
- Eval tests can run deterministically enough for local verification.

## Evidence expectations

Record evidence with:

- eval command and result,
- scenario names,
- metrics used,
- notable false positives/false negatives or limits.

## Progress and notes

- 2026-07-08: Ticket opened from parent Birding Trip Copilot plan.
- 2026-07-09: Added `deepeval>=4.0.7` as a workspace dev dependency, `task eval:agent`, docs command notes, and deterministic DeepEval tests in `tests/evals/test_birding_trip_copilot_deepeval.py`.
- 2026-07-09: Covered `golden-thumb-butte-morning-trip-plan` and `sparse-location-source-unavailable-caveats` scenarios. Metrics check exact expected tool use, persisted evidence/provenance, unavailable-source caveats, and absence of personal life-list/history assumptions.
- 2026-07-09: Validated `task eval:agent`, focused planner/Open-Meteo pytest, ruff, format check, and mypy. See `.10x/evidence/2026-07-09-birding-agent-deepeval-suite.md`.
- 2026-07-09: Repaired CI drift caused by DeepEval's unpinned `aiohttp` dependency resolving to `aiohttp 3.14.1`, which is incompatible with `pytest-recording`/`vcrpy 8.1.1`'s aiohttp stubs. Added scoped workspace dev pin `aiohttp<3.14`; focused VCR-backed source tests and `task ci` pass.

## Blockers

None.
