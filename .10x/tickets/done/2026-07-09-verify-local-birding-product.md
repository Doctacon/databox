Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-build-local-birding-copilot-product.md
Depends-On: .10x/tickets/done/2026-07-09-decommission-motherduck-platform-support.md, .10x/tickets/done/2026-07-09-implement-shared-quack-parallel-refresh.md, .10x/tickets/done/2026-07-09-integrate-cloudflare-ai-with-adk.md, .10x/tickets/done/2026-07-09-build-local-react-trip-planner.md

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

- 2026-07-09: Initial GLM 4.7 verification recorded a redacted model-selector compatibility issue and required a safe smoke rerun. This historical issue was later superseded and resolved by the GLM 5.2 replacement recorded below.
- 2026-07-09: All four implementation dependencies were complete and review-passed before aggregate verification began.
- 2026-07-09: Fresh `task full-refresh` passed with six source jobs, all 15 actual ingest overlap pairs, non-zero core raw counts, zero persistent `main._dlt*`, clean client state, and SQLMesh production materialization.
- 2026-07-09: SQLMesh tests/state, all 23 production Soda contracts (104 checks), `task ci` (183 tests, 81.78% coverage), offline DeepEval, React/API/build/bundle audit, loopback launch, docs build, active MotherDuck/Dive audit, and sensitive-value audits passed.
- 2026-07-09: The original aggregate GLM 4.7 live retry ended in a safe bounded timeout with no fallback or credential disclosure; this is retained as historical evidence and was later resolved by the completed GLM 5.2 replacement.
- 2026-07-09: Aggregate evidence is `.10x/evidence/2026-07-09-local-birding-product-aggregate-verification.md`. Its original review kept the parent open for the then-unsupported GLM 4.7 live criterion; the subsequent-resolution addendum and GLM 5.2 review now support closure.
- 2026-07-09: Retrospective initially assigned the GLM 4.7 Flash timeout to a bounded follow-up owner.
- 2026-07-09: Subsequent resolution replaced the sole model with GLM 5.2, added strict `response_format.json_schema`, passed 189-test CI and independent review, and produced a successful bounded live smoke with four validated actions. Evidence: `.10x/evidence/2026-07-09-glm-5-2-model-replacement.md`.

## Blockers

None. The live-model gap observed during this verification was subsequently resolved by `.10x/tickets/done/2026-07-09-replace-cloudflare-model-with-glm-5-2.md`.
