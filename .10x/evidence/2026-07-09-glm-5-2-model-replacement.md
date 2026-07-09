Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-replace-cloudflare-model-with-glm-5-2.md, .10x/specs/cloudflare-workers-ai-local-agent.md, .10x/evidence/2026-07-09-glm-5-2-compatibility-probe.md

# GLM 5.2 model replacement evidence

## What was observed

The active Birding Trip Copilot runtime now hard-allows only `@cf/zai-org/glm-5.2`. Cloudflare requests use the fixed HTTPS `api.cloudflare.com` chat-completions endpoint and include OpenAI-compatible `response_format.type=json_schema` with a fixed bounded strict schema matching `GroundedSynthesisResult`.

Local Pydantic validation and exact grounding validation remain in place after Cloudflare's schema-constrained response. No fallback, alternate model, response normalization, validation relaxation, retry, timeout increase, browser inference, or credential-destination change was introduced.

The ignored local `.env` contains the exact GLM 5.2 selector. Because the running verification harness inherited the prior selector as a process environment value, the live task was invoked with only that stale variable unset so central settings read the user's current `.env` value.

## Changed active surfaces

- `packages/databox/databox/agents/cloudflare_workers_ai.py`
  - sole model constant changed to `@cf/zai-org/glm-5.2`,
  - fixed strict JSON Schema added for allowlisted action IDs and exact grounding,
  - request uses `max_completion_tokens=750` and documented `response_format.json_schema`,
  - existing endpoint validation, safe errors, byte bounds, Pydantic parsing, and exact grounding checks retained.
- `tests/test_cloudflare_workers_ai.py`
  - exact model assertion updated,
  - strict schema payload, action enum, no-extra-properties, and output-token bound asserted,
  - alternate-model rejection updated.
- `.env.example`, `Taskfile.yaml`, `README.md`, `docs/commands.md`, and `docs/configuration.md`
  - active model and strict JSON Schema behavior updated.
- Governing `.10x` decision/spec/ticket graph
  - GLM 5.2 active contract recorded; GLM 4.7 decision/history preserved as superseded/terminal evidence.

## Offline validation

### Focused model/planner/API/settings suite

```text
uv run --no-sync ruff check packages/databox/databox/agents/cloudflare_workers_ai.py tests/test_cloudflare_workers_ai.py
uv run --no-sync ruff format --check packages/databox/databox/agents/cloudflare_workers_ai.py tests/test_cloudflare_workers_ai.py
uv run --no-sync mypy packages/databox/databox/agents/cloudflare_workers_ai.py packages/databox/databox/agents/birding_trip_planner.py packages/databox/databox/api.py
uv run --no-sync pytest --no-cov -q tests/test_cloudflare_workers_ai.py tests/test_birding_trip_planner.py tests/test_api.py tests/test_settings.py
```

Results: Ruff and format passed; MyPy passed for three source files; all 38 focused tests passed.

### Deterministic evaluation and frontend security

```text
task eval:agent
task app:check
task app:audit-bundle
```

Results:

- DeepEval passed 2/2 scenarios at 100% without a live model call or token cost.
- React strict typecheck, six Vitest tests, and production build passed.
- Browser bundle audit passed with all three Cloudflare configuration names and all three configured values absent.

### Full CI

```text
task ci
```

Result: passed Ruff, format, MyPy for 70 source files, all 189 tests, 82.01% coverage, secret scan, staging drift, and platform-health drift checks.

### Active-reference and local-selector audit

A bounded `rg` check over active runtime, scripts, tests, React, README, docs, Taskfile, and `.env.example` found zero GLM 4.7 Flash references. A value-safe Python check read `.env` without printing it and confirmed its selector equals the exact GLM 5.2 identifier.

Safe result:

```text
active_glm_4_7_references=0 file_selector_exact_glm_5_2=yes
```

Historical/superseded decisions, evidence, reviews, research, and terminal tickets retain factual GLM 4.7 references.

## Live validation

Command, run once after all offline checks passed:

```text
env -u CF_WORKERS_AI_MODEL_BASE_URL task smoke:cloudflare-ai
```

Result:

```text
Cloudflare Workers AI smoke passed: model=@cf/zai-org/glm-5.2 selected_actions=4
```

The request returned within the existing 30-second bound, parsed as strict `GroundedSynthesisResult`, and passed exact grounding validation. No credential, account identifier, endpoint value, or response body was printed or recorded. No fallback or retry occurred.

## What this supports

- GLM 5.2 is available to the configured Cloudflare account.
- GLM 5.2 satisfies the planner's required strict structured-output contract when the documented JSON Schema response format is sent.
- Offline CI/evals remain deterministic and spend-free.
- Browser assets do not receive Cloudflare configuration.
- The former live-inference blocker is technically resolved pending independent review and aggregate record reconciliation.

## Limits

- The live smoke used a minimal no-warehouse-evidence request; the persisted end-to-end planner remains covered by deterministic integration tests rather than a paid live full trip run.
- Cloudflare documents that JSON Schema generation can still fail for extreme requests; the runtime retains explicit safe malformed-response failure behavior and never weakens grounding validation.
