Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-integrate-cloudflare-ai-with-adk.md, .10x/specs/cloudflare-workers-ai-local-agent.md

# Cloudflare Workers AI ADK integration evidence

## What was observed

The local Google ADK planner now performs required bounded strategy selection through an explicit Cloudflare Workers AI client. The client hard-allows only `@cf/zai-org/glm-4.7-flash`, sends credentials only to the fixed HTTPS `api.cloudflare.com` endpoint, caps input/output sizes, validates exact structured grounding, maps failures to safe typed errors, and suppresses unsafe chained causes and response/transport details.

The model returns only allowlisted action IDs plus exact grounding. Python deterministically renders field-plan prose and retains evidence-derived species rationales, preventing model output from inventing species or evidence claims. A failed model or persistence call cannot return a successful plan; persistence is transactional and failed replacement state is removed.

## Procedure and results

### Focused lint, type checking, tests, and evaluation

Commands:

- `.venv/bin/ruff check ...` and `.venv/bin/ruff format --check ...` over the Cloudflare client, planner, settings, smoke script, and related tests: passed after resolving constant `getattr`/`setattr`, import ordering, and formatting issues.
- `.venv/bin/mypy packages/databox/databox/agents/cloudflare_workers_ai.py packages/databox/databox/agents/birding_trip_planner.py packages/databox/databox/config/settings.py`: passed.
- `uv run --no-sync pytest --no-cov -q tests/test_cloudflare_workers_ai.py tests/test_birding_trip_planner.py tests/test_settings.py tests/evals/test_birding_trip_copilot_deepeval.py`: 30 passed after safety hardening.
- `task eval:agent`: 2 passed with 100% metric success and no token cost. The suite uses deterministic fake/no-op models and performs no live model call.

The tests directly cover the exact model allowlist, fixed Cloudflare HTTPS host, rejection of plain HTTP/arbitrary hosts, token/input/collection bounds, typed settings, secret redaction, formatted-traceback cause suppression (including invalid UTF-8 response bytes), authentication/rate-limit/timeout handling, exact start/end/duration/recommendation/caveat grounding, rejection of free-form factual output, deterministic rendering, async and sync ADK entry behavior, successful model traces, and fatal/atomic persistence failure behavior.

### Final malformed-response review fix

Commands and results:

- `.venv/bin/ruff check packages/databox/databox/agents/cloudflare_workers_ai.py tests/test_cloudflare_workers_ai.py`: passed.
- `.venv/bin/ruff format --check packages/databox/databox/agents/cloudflare_workers_ai.py tests/test_cloudflare_workers_ai.py`: passed; both files already formatted.
- `uv run --no-sync pytest --no-cov -q tests/test_cloudflare_workers_ai.py`: 20 passed.

An offline regression response containing invalid UTF-8 now maps to `CloudflareMalformedResponseError` with its cause suppressed. Its formatted traceback contains neither the response-byte marker nor `UnicodeDecodeError` details.

### Compatibility-fix verification

Commands and results:

- `.venv/bin/ruff check packages/databox/databox/agents/cloudflare_workers_ai.py tests/test_cloudflare_workers_ai.py` and matching `ruff format --check`: passed.
- `.venv/bin/mypy packages/databox/databox/agents/cloudflare_workers_ai.py`: passed with no issues.
- The final focused suite passed 30 tests; the exact selector derives the official endpoint, while plain HTTP, arbitrary hosts, duplicate/unknown actions, free-form output, oversized inputs, and changed end times fail closed.
- `task eval:agent`: 2 passed with 100% metric success and no token cost; deterministic fake/no-op models made no live model calls.

### Live Cloudflare smoke

Command: `task smoke:cloudflare-ai`

Result: the client reached the live model endpoint using the derived official URL, but the request ended in the bounded read timeout and raised the safe `CloudflareTimeoutError`. A separate token-verification request returned HTTP 200, confirming network reachability and token validity without printing credentials. Both OpenAI-compatible and native model invocations timed out, so live model success remains externally blocked. No fallback was selected.

### Full CI

Command: `task ci`

Result: passed.

- Ruff check and format passed for 100 files.
- mypy passed for 69 source files.
- 176 pytest tests passed.
- Coverage was 81.29%, above the 70% gate.
- Secret scan passed.
- Staging and platform-health drift checks passed.

## What this supports

This evidence supports the implementation, allowlist, structured grounding, safe failure behavior, failure persistence semantics, offline fake-client/DeepEval behavior, documentation, and CI criteria in `.10x/specs/cloudflare-workers-ai-local-agent.md` and the owning ticket.

## Limits

The live account/model invocation is not proven because the request timed out before a Cloudflare response. The exact-selector derivation and non-HTTP rejection paths are proven deterministically, but they do not prove remote availability or account entitlement. Final aggregate verification owns rerunning `task smoke:cloudflare-ai`; the runtime did not switch models.
