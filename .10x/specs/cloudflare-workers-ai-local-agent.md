Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Cloudflare Workers AI Local Agent

## Purpose and scope

This spec governs Cloudflare Workers AI inference inside the local Python/Google ADK Birding Trip Copilot runtime.

Cloudflare provides remote model inference only. No Cloudflare Worker is deployed and no Wrangler process is required for the local product.

## Runtime contract

- Python and Google ADK MUST own the local agent runtime.
- The ADK workflow MUST retain bounded evidence tools and deterministic persistence safeguards.
- Cloudflare Workers AI MUST power model-generated planning/synthesis behavior through a small model-client boundary.
- The model MUST NOT be allowed to execute arbitrary SQL or bypass mandatory evidence steps.

## Model contract

The only permitted model is Cloudflare's official identifier:

`@cf/zai-org/glm-4.7-flash`

The user's requested `zai-org/glm-4.7-flash` is treated as the human-readable model name; Cloudflare requires the provider-qualified `@cf/` identifier for Workers AI calls.

The runtime MUST NOT silently use Gemini, another Google model, another Cloudflare model, or any fallback model. If the configured model is unavailable, the plan run MUST fail or persist an explicit model-unavailable state.

## Configuration and secrets

The local Python process MUST read these values from `.env`/environment through the central settings boundary:

- `CF_WORKERS_AI_API_KEY`
- `CF_WORKERS_AI_ACCOUNT_ID`
- `CF_WORKERS_AI_MODEL_BASE_URL`

These values MUST NOT be:

- embedded in the React bundle,
- sent to the browser,
- committed,
- written into `.10x` records,
- logged in request/response traces.

`.env.example` MUST document names and safe placeholders only.

## Model input/output behavior

The model input MUST be grounded in bounded tool results and include only the data needed to produce the field-ready plan and species rationales.

The model output MUST be validated before persistence. At minimum it MUST preserve:

- requested location/window/duration,
- high-likelihood and uncommon-plausible sections,
- evidence/source caveats,
- no invented personal sightings or life-list history.

Model prose MUST NOT create source evidence. Persisted evidence and tool traces remain derived from actual tool calls.

## Failure behavior

- Missing Cloudflare configuration MUST produce a user-friendly local readiness/error response.
- Authentication, rate-limit, timeout, malformed response, and unavailable-model failures MUST be distinguishable in logs/traces without exposing secrets.
- A failed model call MUST NOT persist a completed plan.
- Retries, if implemented, MUST be bounded and MUST not switch models.

## Evaluation

Unit and DeepEval coverage MUST use a deterministic fake model client by default. CI MUST NOT require live Cloudflare calls or consume inference spend.

A separate opt-in smoke command MAY call live Cloudflare Workers AI and MUST assert that the configured model is exactly `@cf/zai-org/glm-4.7-flash`.

## Acceptance criteria

- A local ADK trip-plan run calls the configured Cloudflare endpoint with only `@cf/zai-org/glm-4.7-flash`.
- Secrets stay server-side and are absent from browser assets/logs/records.
- Grounded output validation and explicit failure handling are tested.
- Existing deterministic test/eval workflows remain offline and green.
- An opt-in live smoke proves the configured Cloudflare account can invoke the required model.
