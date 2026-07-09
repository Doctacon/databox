Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-replace-cloudflare-model-with-glm-5-2.md
Verdict: pass

# GLM 5.2 model replacement review

## Target

The sole-model replacement governed by:

- `.10x/tickets/done/2026-07-09-replace-cloudflare-model-with-glm-5-2.md`
- `.10x/decisions/local-only-birding-product-architecture.md`
- `.10x/specs/cloudflare-workers-ai-local-agent.md`
- `.10x/evidence/2026-07-09-glm-5-2-compatibility-probe.md`
- `.10x/evidence/2026-07-09-glm-5-2-model-replacement.md`

## Findings

Independent review found no blocker:

- the runtime hard-allows only `@cf/zai-org/glm-5.2` and rejects alternate models,
- credentials can reach only the derived fixed HTTPS `api.cloudflare.com` endpoint,
- arbitrary hosts, HTTP, embedded credentials, and nonstandard ports fail before transport,
- the request uses Cloudflare's documented OpenAI-compatible `response_format.type=json_schema` with a fixed strict bounded schema,
- the schema forbids extra properties, bounds collections, and enum-allowlists all actions,
- Pydantic validation and exact location/window/duration/recommendation/caveat grounding remain mandatory after model output,
- safe error translation suppresses response bodies, transport details, and unsafe causes,
- no fallback, retry, timeout increase, parser repair, or validation weakening was introduced,
- API readiness uses the same strict client validation,
- active runtime/docs contain no GLM 4.7 model contract; remaining references are historical, superseded, terminal, or migration rationale,
- the former decision and timeout ticket are preserved under superseded/cancelled history,
- focused tests, full CI, offline DeepEval, frontend checks, bundle audit, strict-schema diagnostic, and bounded live smoke support the evidence claims.

The reviewer intentionally did not rerun live inference. The recorded live smoke used the exact production client after offline validation and returned four validated actions.

## Verdict

Pass. The model replacement is closure-ready with no unowned finding.

## Residual risk

The live smoke is a minimal no-warehouse-evidence request rather than a paid end-to-end trip. Complete persisted-trip behavior remains covered by deterministic integration tests. Cloudflare may still return safe explicit structured-output failures for extreme requests; the runtime retains fail-closed handling.
