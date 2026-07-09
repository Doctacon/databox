Status: superseded
Created: 2026-07-09
Updated: 2026-07-09

# Cloudflare Birding Agent Workflow

Superseded by `.10x/specs/cloudflare-workers-ai-local-agent.md`; Cloudflare now provides model inference only and no Worker product is deployed.

## Purpose and scope

This spec governs the live server-side agent workflow that the Birding Trip Copilot Dive can access.

It supersedes the local MVP's Python/Google ADK runtime requirement only for live product mode. The existing Python planner remains a local/dev reference and evaluation harness unless a later ticket removes or replaces it.

## Runtime ownership

A Cloudflare Worker API MUST own live trip-planning workflow execution for the Dive.

The Worker MUST run server-side. The MotherDuck Dive MUST NOT execute the agent in browser code and MUST NOT contain private API tokens.

## Configuration and secrets

The Worker MUST read these secrets/config values from environment-managed Worker secrets or deployment environment, not from committed files or Dive source:

- `MOTHERDUCK_TOKEN`
- `CF_WORKERS_AI_API_KEY`
- `CF_WORKERS_AI_ACCOUNT_ID`
- `CF_WORKERS_AI_MODEL_BASE_URL`

The Worker MUST use only this model for live agent/model calls:

- `zai-org/glm-4.7-flash`

If that model or endpoint is unavailable, the Worker MUST return and persist an explicit unavailable/error state. It MUST NOT silently fall back to another model.

The model-client boundary SHOULD be small and replaceable so a future open/self-hosted model can replace Cloudflare Workers AI without changing the Dive or MotherDuck persistence contract.

## Access control

Workflow-trigger endpoints MUST be protected by Cloudflare Access or an equivalent identity gate.

The Worker MUST NOT rely on browser-side shared secrets for authorization.

The Worker MUST also enforce non-identity guardrails:

- accepted request schema validation,
- bounded duration and date windows,
- bounded text field lengths,
- rate and/or concurrency limits appropriate for the deployment,
- clear errors for invalid input,
- no logging of secrets or unnecessary personal data.

## API behavior

The Worker SHOULD expose a small HTTP API:

- `GET /health` returns service/config readiness without exposing secrets.
- `POST /api/trip-plans` accepts a trip-planning request and creates or updates a persisted trip plan.
- `GET /api/trip-plans/:trip_plan_id` returns persisted status/summary for polling.

A trip-planning request MUST include:

- location,
- start date/time,
- duration minutes.

It MAY include:

- skill level,
- constraints,
- client idempotency key.

The Worker MUST return a stable `trip_plan_id` for created plans.

## Agentic workflow behavior

The Worker MUST behave as an evidence-seeking agent, not a single ungrounded text generator. It MUST sequence bounded tool steps that cover:

1. normalize/resolve requested location,
2. query MotherDuck eBird recent-observation evidence where available,
3. query MotherDuck GBIF occurrence context where available,
4. fetch request-time Open-Meteo context or persist an unavailable caveat,
5. query MotherDuck Xeno-canto media context where available,
6. rank likely and uncommon-plausible species,
7. synthesize field-ready plan prose through `zai-org/glm-4.7-flash`,
8. persist plan, recommendations, evidence, and tool traces.

The Worker MUST NOT silently skip a required evidence family. Missing evidence MUST be represented as source-unavailable caveats in persisted evidence/tool traces and in the returned plan summary.

## Persistence behavior

The Worker MUST persist outputs into MotherDuck tables/views suitable for the Dive.

At minimum, persistence MUST support these logical grains:

- one row per trip plan,
- one row per recommended species per trip plan,
- one row per evidence item per recommended species or per trip plan,
- one row per tool call/trace step per trip plan.

Persistence MUST be compatible with `.10x/specs/superseded/motherduck-live-publication.md`: cloud-generated trip-plan artifacts MUST survive subsequent warehouse snapshot publishes.

## Acceptance criteria

- A deployed or locally runnable Worker can create a trip plan using Cloudflare Workers AI with only `zai-org/glm-4.7-flash`.
- The Worker reads all private tokens from environment-managed secrets and exposes none to the Dive/browser.
- Cloudflare Access or equivalent identity gating protects workflow-trigger endpoints.
- The Worker queries MotherDuck evidence, calls Open-Meteo, calls the configured model, and persists traceable outputs.
- The Worker returns explicit unavailable/error states for missing sources or model/API failures.
- Persisted outputs can be rendered by the Birding Trip Copilot Dive.
