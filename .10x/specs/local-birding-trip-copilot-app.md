Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Local Birding Trip Copilot React App

## Purpose and scope

This spec governs the local React product surface and local Python API for creating and viewing Birding Trip Copilot plans.

It replaces the MotherDuck Dive surface governed by the superseded `.10x/specs/superseded/birding-trip-plan-dive.md`.

## Architecture

- A Vite + React + TypeScript frontend provides the browser UI.
- A local Python HTTP API provides trip-plan commands and reads persisted artifacts.
- The Python API invokes the Google ADK planner governed by `.10x/specs/cloudflare-workers-ai-local-agent.md`.
- Both servers bind to loopback by default.
- The Python API is the only browser-facing component that accesses `data/databox.duckdb`.
- The frontend MUST NOT receive database or Cloudflare credentials.

The implementation SHOULD repurpose useful presentation code from the existing Dive artifact only when doing so is smaller than rebuilding it. MotherDuck SDK/query hooks and Dive metadata MUST be removed.

## User workflow

The app MUST let a user:

1. open a local URL,
2. enter location, start date/time, duration, optional skill level, and optional constraints,
3. submit a trip-planning request,
4. see clear running/success/failure state,
5. view the persisted field plan,
6. inspect weather/elevation context,
7. inspect high-likelihood and uncommon-plausible species with one persisted photo and call result per recommendation,
8. inspect evidence/provenance as the final result section,
9. inspect agent tool traces inside an accessible disclosure within Evidence and Provenance,
10. select and revisit previous persisted plans.

The exact result order, recommendation-card media behavior, attribution, placeholders, and removal of the standalone media section are governed by `.10x/specs/recommendation-card-media-layout.md`.

The app MUST NOT require a user account or personal life-list/history.

## API contract

The local API SHOULD expose:

- `GET /api/health` — database/config/model readiness without secrets,
- `GET /api/trip-plans` — recent persisted plan summaries,
- `POST /api/trip-plans` — validate and execute one trip-planning request,
- `GET /api/trip-plans/{trip_plan_id}` — complete plan/recommendation/evidence/trace view.

`POST /api/trip-plans` MUST accept:

- `location`: non-empty bounded string,
- `start_at`: valid ISO local timestamp,
- `duration_minutes`: positive bounded integer,
- optional `skill_level`,
- optional `constraints`.

The API MUST use stable JSON response shapes and user-friendly errors. It MUST NOT expose stack traces or secrets.

For the first local-only version, one plan request MAY execute synchronously if the UI shows progress and the call remains bounded. A queue/background-job system MUST NOT be introduced without measured need.

## Database behavior

- Plans, recommendations, evidence, and tool traces MUST persist in `birding_agent.*` inside `data/databox.duckdb`.
- The API MUST read those persisted artifacts for result pages rather than trusting transient model output.
- API access MUST not run while a refresh holds an incompatible exclusive local database lifecycle. The UI MUST surface a clear temporarily-unavailable state rather than corrupting or bypassing Quack ownership.

## UX and accessibility

- Forms MUST use semantic labels and native controls.
- Submit controls MUST expose disabled/loading state.
- Errors and empty states MUST be visible text, not color alone.
- Evidence and external media links MUST include source/attribution and open safely.
- The UI SHOULD retain the existing Birding Trip Copilot story rather than becoming a generic warehouse explorer.

## Developer workflow

A single documented task SHOULD launch the local API and React dev server. A production-style local build SHOULD allow the Python API to serve the compiled React assets or provide an equally simple one-command local launch.

## Acceptance criteria

- A user can create and revisit a trip plan entirely through the local React app.
- The app renders persisted recommendations, weather context, recommendation-centric photo/call media, evidence, caveats, and tool traces in the order governed by `.10x/specs/recommendation-card-media-layout.md`.
- Only the local Python process accesses DuckDB and Cloudflare credentials.
- The app handles loading, empty, invalid-input, model-unavailable, source-unavailable, and database-busy states.
- Frontend type/build tests and Python API tests pass.
- The local run command and prerequisites are documented.
