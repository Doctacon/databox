Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-replace-cloudflare-model-with-glm-5-2.md, .10x/specs/cloudflare-workers-ai-local-agent.md

# GLM 5.2 fail-fast compatibility probe

## What was observed

One bounded live request was sent to Cloudflare's fixed HTTPS OpenAI-compatible chat-completions endpoint using exactly `@cf/zai-org/glm-5.2` from the ignored local `.env`.

Cloudflare returned HTTP 200 within the 30-second bound, proving that the configured account can reach and invoke the model. The returned message content did not validate as the required `GroundedSynthesisResult` structured JSON contract used by the Birding Trip Copilot.

No response body, credential, account identifier, endpoint value, or configured secret was printed or recorded. No fallback model was attempted.

## Procedure

The temporary stdin probe:

- explicitly loaded `.env` with override enabled because the parent shell retained the prior exported selector,
- asserted the selector was exactly `@cf/zai-org/glm-5.2`,
- used the existing bounded planner system prompt and `GroundedSynthesisRequest`,
- sent one request with temperature zero, 512 maximum output tokens, and a 30-second timeout,
- required HTTP 200,
- parsed the OpenAI-compatible `choices[0].message.content`,
- validated it with the existing `GroundedSynthesisResult` model and exact grounding checks.

Result:

```text
probe_failed=response was not the required structured JSON shape
```

The HTTP-status guard ran before structured parsing, so this result implies HTTP 200 rather than authentication, entitlement, rate-limit, timeout, or transport failure.

Two earlier harness attempts made no network request: one failed during stdin `.env` discovery and one observed the stale inherited process selector before transport. The corrected probe made exactly one live inference request.

## What this supports or challenges

Supports:

- GLM 5.2 is available to the configured Cloudflare account.
- The fixed HTTPS endpoint and credentials can invoke it without timing out.

Challenges:

- GLM 5.2 is not a drop-in replacement for the planner's current prompt/parser contract based on this single probe.
- Runtime allowlist replacement alone would produce malformed-response failures rather than working plans.

## Corrected strict-schema diagnostic

The user identified Cloudflare's OpenAI-compatible structured-output support. Official Cloudflare documentation and the GLM 5.2 synchronous input schema were then inspected:

- `https://developers.cloudflare.com/workers-ai/features/json-mode/`
- `https://developers.cloudflare.com/workers-ai/models/glm-5.2/sync-input.json`

The model-specific input schema explicitly supports OpenAI-style `response_format` values `text`, `json_object`, and `json_schema`. For `json_schema`, Cloudflare accepts `name`, `description`, `schema`, and `strict`.

One corrected bounded diagnostic added `response_format.type=json_schema` with an inline strict schema matching `GroundedSynthesisResult`. It retained temperature zero, a bounded 750-token output, the existing planner prompt/request, the fixed HTTPS endpoint, and the 30-second timeout.

Safe result:

```text
diagnostic_passed=model=@cf/zai-org/glm-5.2 strict_json_schema=yes grounding_exact=yes actions=3 elapsed_seconds=10.46
```

The returned content passed the existing Pydantic result model and exact location/window/duration/recommendation/caveat grounding checks. No body or credential was printed or retained. No fallback was attempted.

## Conclusion

GLM 5.2 is compatible with the planner's strict structured-output contract when the documented OpenAI-compatible `response_format.json_schema` parameter is supplied. The initial plain-prompt probe challenged only the request construction, not the model capability.

## Limits

- This was one minimal no-warehouse-evidence diagnostic, not a complete trip-plan run.
- Runtime implementation must generate a bounded fixed schema, retain Pydantic and exact-grounding validation, and test malformed/error responses independently.
- The JSON Mode overview's older enumerated model list does not name GLM 5.2, but the current GLM 5.2 model-specific synchronous input schema explicitly includes `response_format.json_schema`; the model-specific schema and successful live diagnostic are the applicable evidence.
