Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-build-local-birding-copilot-product.md
Depends-On: .10x/tickets/done/2026-07-09-integrate-cloudflare-ai-with-adk.md

# Replace Cloudflare model with GLM 5.2

## Scope

Replace the product-wide sole Cloudflare Workers AI model from `@cf/zai-org/glm-4.7-flash` to the user-ratified `@cf/zai-org/glm-5.2`.

Required work:

- set the ignored local configuration to `CF_WORKERS_AI_MODEL_BASE_URL='@cf/zai-org/glm-5.2'`,
- replace the runtime allowlist/model constant and every active validation/error contract,
- update smoke, settings, API readiness, planner, offline eval, and regression tests,
- update active environment examples, tasks, README, and command/configuration docs,
- retain one exact model with no fallback or alternate model,
- preserve fixed HTTPS `api.cloudflare.com` credential delivery, bounded structured output, deterministic factual rendering, safe errors, async execution, and atomic persistence,
- run one bounded live smoke after offline validation,
- update parent progress and create model-specific evidence/review records.

Historical GLM 4.7 Flash evidence, terminal tickets, and superseded decisions MUST remain factual history and MUST NOT be rewritten as GLM 5.2 proof.

## Explicit exclusions

- No fallback to GLM 4.7 Flash or any other model.
- No deployed Worker or Wrangler runtime.
- No browser-side inference or credential exposure.
- No response-body, token, account identifier, or configured-value logging.
- No unrelated planner, UI, Quack, SQLMesh, or CDM behavior changes.
- No unbounded retries or timeout increases.

## Acceptance criteria

- `CLOUDFLARE_WORKERS_AI_MODEL` and every active model assertion equal exactly `@cf/zai-org/glm-5.2`.
- The local ignored `.env` selector is exactly `CF_WORKERS_AI_MODEL_BASE_URL='@cf/zai-org/glm-5.2'`; committed files contain only safe examples.
- GLM 4.7 Flash remains only in clearly historical/superseded/terminal records.
- Invalid model selectors and arbitrary credential destinations are rejected before transport.
- API readiness agrees with strict GLM 5.2 configuration validation.
- Focused tests, Ruff, MyPy, offline DeepEval, frontend bundle audit, and full CI pass without live inference.
- `task smoke:cloudflare-ai` returns one bounded validated response from exactly `@cf/zai-org/glm-5.2` without exposing credentials or using a fallback.
- Aggregate parent records accurately state whether live GLM 5.2 inference is proven.

## Evidence expectations

Record:

- changed active model references and historical exclusions,
- exact focused/offline validation commands and results,
- bundle and configured-value audits without printing values,
- the bounded live-smoke result and safe status,
- final diff/no-staged-file checks,
- independent correctness/security review.

## References

- `.10x/decisions/local-only-birding-product-architecture.md`
- `.10x/specs/cloudflare-workers-ai-local-agent.md`
- `.10x/specs/birding-trip-copilot.md`
- `.10x/specs/birding-agent-evaluations.md`
- `.10x/tickets/done/2026-07-09-build-local-birding-copilot-product.md`
- `.10x/tickets/cancelled/2026-07-09-resolve-cloudflare-workers-ai-live-inference-timeout.md`

## Progress and notes

- 2026-07-09: User explicitly ratified replacing the sole product model with `@cf/zai-org/glm-5.2` and provided the exact local selector assignment. No fallback was authorized.
- 2026-07-09: Fail-fast live compatibility probe reached GLM 5.2 and received HTTP 200, but the message content did not validate because the initial request omitted OpenAI-compatible `response_format`. No implementation files were changed and no fallback was attempted.
- 2026-07-09: After user direction, official Cloudflare JSON Mode and GLM 5.2 input-schema documentation confirmed `response_format.json_schema`. One corrected strict-schema diagnostic passed existing Pydantic and exact-grounding validation in 10.46 seconds. Evidence: `.10x/evidence/2026-07-09-glm-5-2-compatibility-probe.md`.
- 2026-07-09: Replaced the active runtime/model contract with sole model `@cf/zai-org/glm-5.2` and added a fixed bounded strict JSON Schema response format while retaining Pydantic and exact-grounding checks.
- 2026-07-09: Focused Ruff/MyPy/38 tests, offline DeepEval 2/2, React typecheck/6 tests/build, bundle audit, and full CI (189 tests, 82.01% coverage) passed. Active GLM 4.7 runtime/docs references are zero; ignored `.env` selector is exact without printing it.
- 2026-07-09: One post-offline live smoke passed with GLM 5.2 and four validated actions. Evidence: `.10x/evidence/2026-07-09-glm-5-2-model-replacement.md`.
- 2026-07-09: Independent correctness/security review passed with no blocker: `.10x/reviews/2026-07-09-glm-5-2-model-replacement-review.md`.
- 2026-07-09: Retrospective preserved the key provider mechanic in the active spec and compatibility evidence: GLM 5.2 requires the documented strict `response_format.json_schema` request rather than prompt-only JSON instructions. No additional skill or follow-up is required.

## Blockers

None.
