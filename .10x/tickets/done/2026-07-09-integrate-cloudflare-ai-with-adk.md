Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/2026-07-09-build-local-birding-copilot-product.md
Depends-On: .10x/tickets/done/2026-07-09-implement-shared-quack-parallel-refresh.md

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

- 2026-07-09: Added typed central Cloudflare settings and an explicit OpenAI-compatible Workers AI client hard-allowing only `@cf/zai-org/glm-4.7-flash`.
- 2026-07-09: Integrated grounded structured synthesis into the bounded ADK planner before persistence, with safe model traces and cleanup of stale completed artifacts on failure.
- 2026-07-09: Added deterministic client/planner tests and offline DeepEval coverage for grounding, allowlisting, safe errors, redaction, persistence, and source caveats.
- 2026-07-09: Repaired Ruff findings and ADK synchronous exception swallowing; focused tests/mypy, `task eval:agent`, and `task ci` passed.
- 2026-07-09: Live smoke initially failed closed before HTTP because the existing local base-URL value has model-identifier rather than HTTP(S) endpoint shape.
- 2026-07-09: Added the approved compatibility behavior: the exact allowlisted identifier derives Cloudflare's official account-specific chat-completions endpoint, while every other non-HTTP value remains rejected.
- 2026-07-09: Follow-up security review found credential-destination, exception-cause, cost-bound, end-time, async, persistence, arbitrary-model, and free-form grounding gaps. All were repaired with fixed-host HTTPS delivery, strict bounds, exact grounding, async/thread-safe ADK entry points, atomic fatal persistence, contract-only ADK descriptor, and bounded action selection with deterministic rendering.
- 2026-07-09: Final focused suite passed 30 tests; mypy passed; offline DeepEval passed 2/2 with no model cost; full CI passed 176 tests at 81.29% coverage. Live model smoke still timed out after reaching the authenticated Cloudflare route; no fallback or secret logging occurred.

## Evidence and review

- `.10x/evidence/2026-07-09-cloudflare-workers-ai-adk-integration.md`
- `.10x/reviews/2026-07-09-cloudflare-workers-ai-adk-integration-review.md`

## Blockers

No implementation blocker. The local value-shape blocker is resolved. Live account invocation remains externally unproven because both the compatibility-fix smoke and the aggregate retry in `.10x/tickets/done/2026-07-09-verify-local-birding-product.md` timed out without a response. `.10x/tickets/2026-07-09-resolve-cloudflare-workers-ai-live-inference-timeout.md` owns the continuing external investigation. No fallback model was used.
