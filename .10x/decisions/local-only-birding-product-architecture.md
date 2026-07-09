Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Local-only Birding Trip Copilot architecture

## Context

The existing Birding Trip Copilot MVP persists plans to DuckDB and includes a MotherDuck Dive-as-code artifact. A short-lived follow-up direction considered publishing local data to MotherDuck and deploying a Cloudflare Worker product shell. Research exposed deployment, authentication, data synchronization, and write-boundary complexity that does not serve the user's actual goal: a personal local product with no deployment plan.

The user ratified:

- local React app as the product surface,
- Python/Google ADK as the local agent runtime,
- Cloudflare Workers AI as the remote model-inference provider,
- only the GLM 4.7 Flash model,
- complete removal of active MotherDuck support and Dive artifacts,
- required concurrent source loading through one shared Quack server into one local DuckDB.

This decision supersedes `.10x/decisions/superseded/live-motherduck-cloudflare-agent-architecture.md`.

## Decision

Databox will be a local-only product:

1. `data/databox.duckdb` is the only data warehouse and application-state database.
2. One local Quack server owns that file during refresh. Independent hermetic dlt source clients MUST load concurrently through the Quack protocol; direct multi-process file connections are prohibited.
3. SQLMesh materializes transformations locally after source loading.
4. A local Python API owns database writes and invokes the existing Google ADK workflow.
5. A local React app is the user-facing Trip Planner and result/evidence/tool-trace viewer. It calls only the local Python API and never opens DuckDB directly.
6. The Python ADK workflow calls Cloudflare Workers AI for model inference through an explicit model-client boundary.
7. The only allowed model identifier is Cloudflare's official `@cf/zai-org/glm-4.7-flash`. No fallback model is permitted.
8. Cloudflare credentials remain local server-side environment variables. They MUST NOT be exposed to the React bundle or browser.
9. Active MotherDuck backend support, configuration, tests, docs, and Dive artifacts will be removed. Historical changelog and terminal `.10x` records may retain factual MotherDuck references as history.

## Alternatives considered

- **MotherDuck + saved/embedded Dive**: rejected because it adds deployment, authentication, synchronization, and cloud app-state concerns without a deployment need.
- **Cloudflare Worker as deployed runtime**: rejected because the product is local and does not need a deployed application or Cloudflare Access.
- **Local Wrangler Worker process**: rejected because it adds a second runtime process without benefit; Python can call the Workers AI HTTP endpoint directly.
- **Streamlit UI**: simpler, but rejected by the user in favor of a local React product surface.
- **Sequential Quack jobs**: current reliable behavior, but rejected by the user; shared-server parallel loading is a required contract and must block if it cannot be made safe.
- **Remove Google ADK**: rejected; the user chose Python/Google ADK plus Cloudflare inference.

## Consequences

- The local app needs a small Python HTTP API and React frontend.
- Existing `.dive-preview` code can be removed or repurposed, but no MotherDuck browser SDK or token may remain.
- The Cloudflare dependency remains a narrow exception to Open Source First for model inference only. The model client must stay replaceable.
- The local API should bind to loopback by default and needs no deployment authentication in this scope.
- Parallel Quack behavior requires a focused protocol/state investigation before it can be claimed complete.
- MotherDuck removal is a repository-wide active-capability migration and must repair ADR/docs/config/test references coherently.
