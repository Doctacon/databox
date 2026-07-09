Status: open
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/2026-07-09-build-local-birding-copilot-product.md
Depends-On: .10x/tickets/2026-07-09-decommission-motherduck-platform-support.md, .10x/tickets/2026-07-09-implement-shared-quack-parallel-refresh.md, .10x/tickets/2026-07-09-integrate-cloudflare-ai-with-adk.md, .10x/tickets/2026-07-09-build-local-react-trip-planner.md

# Verify local Birding Trip Copilot product

## Scope

Perform aggregate verification, adversarial review, documentation coherence checks, and closure readiness for the local-only product parent plan.

This ticket verifies and records; it does not silently widen or repair child implementation scope. Any discovered defect requires reopening its owning child or creating a bounded follow-up.

## Acceptance criteria

- Every parent and child criterion maps to durable evidence.
- `task full-refresh` proves one shared Quack server and concurrent hermetic source clients.
- SQLMesh and quality contracts pass against `data/databox.duckdb`.
- A local React/API run creates and reloads a persisted trip plan.
- The plan uses only `@cf/zai-org/glm-4.7-flash` for model-generated behavior.
- Browser assets/logs/records expose no Cloudflare credentials.
- Offline CI/evals require no paid/live inference.
- Opt-in Cloudflare smoke passes or a precise external blocker is owned.
- Active runtime/config/docs/tests contain no MotherDuck/Dive support.
- Relevant specs match observed implementation behavior.
- Final independent review returns pass or all findings are durably owned.

## Required checks

At minimum, run the current repository equivalents of:

- Python lint/format/typecheck/tests/secret scan,
- SQLMesh tests and local production refresh,
- source-layout/platform-health checks,
- DeepEval offline suite,
- frontend lint/typecheck/tests/build,
- local API contract tests,
- local end-to-end product scenario,
- active-reference audit for MotherDuck/Dive,
- generated docs check/build.

## Evidence expectations

Create aggregate evidence with exact commands, dates, output summaries, logs/artifacts, and limits. Create an adversarial review record. Do not close parent/children unless closure coherence and retrospective protocol are satisfied.

## Progress and notes

None.

## Blockers

Depends on all implementation children.
