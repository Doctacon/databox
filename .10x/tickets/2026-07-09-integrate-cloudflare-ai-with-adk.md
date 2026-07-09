Status: open
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/2026-07-09-build-local-birding-copilot-product.md
Depends-On: .10x/tickets/2026-07-09-implement-shared-quack-parallel-refresh.md

# Integrate Cloudflare Workers AI with local Google ADK planner

## Scope

Implement `.10x/specs/cloudflare-workers-ai-local-agent.md` in the existing Python/Google ADK Birding Trip Copilot.

Required work:

- add typed central settings for the three Cloudflare env vars,
- add an explicit model client using the configured Cloudflare Workers AI endpoint,
- hard-code/allowlist only `@cf/zai-org/glm-4.7-flash`,
- use model output for grounded field-plan/species-rationale synthesis inside the bounded ADK workflow,
- validate output before completion/persistence,
- persist model call trace/status without secrets,
- add deterministic fake-client tests and offline DeepEval coverage,
- add an opt-in live smoke command/test that consumes the real `.env` credentials.

## Explicit exclusions

- Do not deploy a Cloudflare Worker or use Wrangler.
- Do not expose Cloudflare values through the API/browser.
- Do not add fallback models.
- Do not permit arbitrary model-generated SQL or source skipping.
- Do not add personal history/life-list behavior.

## Acceptance criteria

- A local ADK run invokes the model boundary with exactly `@cf/zai-org/glm-4.7-flash`.
- The configured base URL/account/API key are read from central settings and redacted from logs/traces.
- Grounded structured output is validated before completed-plan persistence.
- Missing config, auth, rate limit, timeout, malformed response, and unavailable-model behavior are user-legible and tested.
- Default unit/DeepEval tests perform no live model calls.
- Opt-in live smoke succeeds against the user's configured account or records a precise external blocker.
- Existing plan/recommendation/evidence/tool-trace contract remains compatible with the local API app spec.

## Evidence expectations

Record:

- offline tests and DeepEval results,
- model allowlist assertion,
- secret-redaction check,
- opt-in live smoke result with request identifiers only if non-sensitive,
- persisted artifact inspection.

## Progress and notes

None.

## Blockers

None; required env variable names are user-ratified and present in `.env`. Credential validity is verified only by the opt-in live smoke.
