Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Local-only Birding Trip Copilot architecture

## Context

The Birding Trip Copilot is a personal local product. Earlier work removed MotherDuck/Dive deployment complexity, established one Quack-backed DuckDB, retained Python/Google ADK, and allowed Cloudflare Workers AI only as remote inference.

The initial architecture selected `@cf/zai-org/glm-4.7-flash`. Live requests repeatedly reached Cloudflare but timed out before a model response. The user has now explicitly replaced that model contract with `@cf/zai-org/glm-5.2`, using `CF_WORKERS_AI_MODEL_BASE_URL='@cf/zai-org/glm-5.2'` and retaining the no-fallback rule.

This decision supersedes `.10x/decisions/superseded/local-only-birding-product-architecture-glm-4-7-flash.md`. All non-model local-only architecture constraints remain unchanged.

## Decision

Databox will be a local-only product:

1. `data/databox.duckdb` is the only data warehouse and application-state database.
2. One local Quack server owns that file during refresh. Independent hermetic dlt source clients MUST load concurrently through the Quack protocol; direct multi-process file connections are prohibited.
3. SQLMesh materializes transformations locally after source loading.
4. A local Python API owns database writes and invokes the Google ADK workflow.
5. A local React app is the user-facing Trip Planner and result/evidence/tool-trace viewer. It calls only the local Python API and never opens DuckDB directly.
6. The Python ADK workflow calls Cloudflare Workers AI through an explicit model-client boundary.
7. The only allowed model identifier is `@cf/zai-org/glm-5.2`. No fallback or alternate model is permitted.
8. The local model selector is `CF_WORKERS_AI_MODEL_BASE_URL='@cf/zai-org/glm-5.2'`; the client derives Cloudflare's fixed HTTPS endpoint and never sends credentials to another host.
9. Cloudflare credentials remain local server-side environment variables. They MUST NOT be exposed to the React bundle or browser.
10. MotherDuck backend support, configuration, tests, docs, and Dive artifacts remain removed. Historical changelog and terminal `.10x` records may retain factual MotherDuck references as history.

## Alternatives considered

- **Keep `@cf/zai-org/glm-4.7-flash`**: rejected after repeated bounded live timeouts and the user's explicit replacement direction.
- **Use both GLM models or fallback automatically**: rejected because fallback would weaken reproducibility and hide provider/model failures.
- **MotherDuck or a deployed Cloudflare Worker**: rejected because the product remains local and needs neither cloud warehousing nor deployment.
- **Local Wrangler Worker process**: rejected because Python can call Workers AI directly.
- **Remove Google ADK**: rejected; Python/Google ADK remains the chosen local agent runtime.

## Consequences

- The model constant, settings validation, tests, DeepEval assertions, docs, examples, and smoke command must change together.
- Existing structured grounding, deterministic factual rendering, bounded request/output, safe errors, async execution, and atomic persistence constraints remain mandatory.
- Historical evidence for GLM 4.7 Flash remains historical and must not be rewritten as proof for GLM 5.2.
- Parent closure requires a successful bounded live GLM 5.2 inference or a newly ratified acceptance change.
