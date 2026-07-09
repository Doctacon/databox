Status: active
Created: 2026-07-08
Updated: 2026-07-08

# Birding Agent Evaluations

## Purpose and scope

This spec governs first-slice DeepEval coverage for the Birding Trip Copilot.

The goal is to prove the planner behaves like an evidence-seeking agent, not merely a text generator.

## Evaluation scope

The first implementation MUST include DeepEval in the MVP slice.

Evaluations SHOULD cover:

- expected tool use for a trip-planning request,
- final answer quality for at least one golden scenario,
- explicit handling of unavailable evidence sources,
- absence of personal-life-list assumptions,
- presence of evidence/provenance in the answer or persisted artifacts.

## Golden scenario expectations

At least one golden scenario MUST represent a realistic hobbyist request such as:

> "I have 90 minutes tomorrow morning near Thumb Butte. What should I try to see?"

The test case MUST assert that the planner uses tools for observation/context lookup, weather/elevation, ranking, and persistence. It MUST NOT accept a single ungrounded LLM response as passing.

## Tool-use expectations

DeepEval tests SHOULD use tool-oriented metrics where possible, such as tool correctness or tool-use metrics, to compare expected tools against observed tool calls. Exact metric class names and API usage MUST be verified against the installed DeepEval version during implementation.

## Quality expectations

The first eval suite SHOULD prefer small, deterministic, local fixtures over live external API calls. Live API behavior MAY be covered by separate integration tests, but the DeepEval suite SHOULD remain stable enough for CI or local verification.

## Acceptance criteria

- DeepEval is added to project dependencies or dependency groups in a scoped way.
- At least one golden trip-planning scenario can run locally.
- The eval checks expected tool use rather than only final text similarity.
- The eval checks that output includes evidence/provenance or references persisted evidence artifacts.
- The eval checks that no stored personal history/life-list assumption is used in the MVP.
- The eval command/path is documented for future runs.
