Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/2026-07-09-build-local-birding-copilot-product.md
Depends-On: .10x/tickets/done/2026-07-09-integrate-cloudflare-ai-with-adk.md

# Build local React Trip Planner product

## Scope

Implement `.10x/specs/local-birding-trip-copilot-app.md` as a Vite + React + strict TypeScript frontend and local Python HTTP API.

Required work:

- replace the old Streamlit explorer/local Dive preview with the focused Trip Planner product,
- add the bounded health/list/create/detail API contract,
- invoke the existing local ADK planner through the create endpoint,
- read completed results from persisted `birding_agent.*` artifacts,
- implement form, running/error/empty states, plan history/selector, field plan, species groups, weather/elevation, evidence, media/license links, caveats, and tool traces,
- bind local servers to loopback by default,
- provide one-command development and built-local launch paths,
- add frontend and API tests.

## Explicit exclusions

- No user accounts, personal history, life list, deployment, Cloudflare Worker, MotherDuck, or Dive runtime.
- No background queue unless synchronous execution fails a measured bounded usability requirement.
- No browser direct DuckDB access or Cloudflare credentials.
- No generic warehouse explorer unless needed by a named Trip Planner acceptance criterion.

## Acceptance criteria

- A user can create a plan from the React app and revisit it after page reload.
- Form inputs and API validation match the governing spec.
- The result view renders persisted plan, recommendations, weather, evidence/provenance, media/license links, caveats, and tool traces.
- Loading, empty, invalid-input, model-unavailable, source-unavailable, and database-busy states are covered.
- Browser assets contain none of the Cloudflare env var values/names as injected secrets.
- Semantic controls, labels, focusability, accessible names, and disabled/loading behavior are preserved.
- Frontend typecheck/test/build and Python API tests pass.
- Local launch documentation is copy-pasteable and verified.

## Evidence expectations

Record:

- API contract tests,
- frontend tests/build,
- browser-visible product screenshots or equivalent captured UI evidence,
- one end-to-end local plan creation against a controlled model client,
- secret/bundle audit,
- launch-command verification.

## Progress and notes

- 2026-07-09: Replaced the Streamlit explorer with a strict Vite/React Trip Planner and loopback FastAPI API.
- 2026-07-09: Added deterministic API persistence/error tests and rendered frontend state/accessibility/security tests.
- 2026-07-09: Verified typecheck, build, built-loopback launch, bundle secret absence, strict docs, pre-commit, and full Python CI (180 passed, 81.25% coverage).
- 2026-07-09: Evidence recorded in `.10x/evidence/2026-07-09-local-react-trip-planner.md`; adversarial review passed in `.10x/reviews/2026-07-09-local-react-trip-planner-review.md`.
- 2026-07-09: Reopened the completed implementation narrowly to repair independent review findings: persisted Xeno-canto recordist attribution, unavailable-media sentinel filtering, explicit typed API response projections/contracts, and an executable configured bundle audit.
- 2026-07-09: Revalidated 6 focused Python tests, 6 frontend tests plus typecheck/build, focused Ruff/MyPy, the configured bundle audit, and full CI (183 passed, 81.78% coverage); review remains pass with no open finding.
- 2026-07-09: Reopened narrowly to repair the final aggregate review defect: health readiness accepted nonempty Cloudflare configuration without enforcing the runtime client's strict endpoint/account/model validation.
- 2026-07-09: Health now reuses strict `CloudflareWorkersAIClient.from_settings` validation or requires an injected client's exact allowlisted model ID, without inference or response-detail changes. Focused Ruff, format, MyPy, and 9 API tests passed; full CI passed 189 tests at 82.01% coverage. Evidence and pass review were updated with the finding and fix.

## Blockers

None.
