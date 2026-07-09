Status: superseded
Created: 2026-07-09
Updated: 2026-07-09

# Live MotherDuck + Cloudflare agent architecture

Superseded by `.10x/decisions/local-only-birding-product-architecture.md` after the user rejected deployment and MotherDuck in favor of a local-only React + Python/ADK product.

## Context

The completed local Birding Trip Copilot MVP uses local Quack-backed DuckDB, SQLMesh, a Python/Google ADK planner, persisted trip-plan artifacts, and a MotherDuck Dive-as-code artifact. The user clarified the intended product shape:

- registered sources load into the single local `data/databox.duckdb` file through Quack,
- the MotherDuck Dive reads product data from MotherDuck,
- the Dive can access an agentic workflow,
- the agent/model layer is powered by the user's Cloudflare Workers AI account using env vars in `.env`,
- only `zai-org/glm-4.7-flash` may be used.

This conflicts with two prior constraints:

- `/Users/crlough/Code/personal/CLAUDE.md` says to always choose open source over proprietary/managed solutions unless explicitly documented.
- `.10x/specs/birding-trip-copilot.md` says the MVP uses Python with Google ADK and `.10x/specs/superseded/birding-trip-plan-dive.md` says the Dive is not itself the agent runtime.

The user explicitly ratified these choices for this workstream:

- Supersede Open Source First for the agent/model layer only.
- Cloudflare Worker owns the live agent workflow.
- Local Quack data reaches MotherDuck through snapshot publication.
- Cloudflare Access protects workflow triggers from the Dive.

## Decision

Databox live Birding Trip Copilot product mode will use this architecture:

1. **Local warehouse refresh**: dlt sources load into `data/databox.duckdb` through Quack, then SQLMesh materializes the local modeled warehouse.
2. **MotherDuck publication**: a native DuckDB/MotherDuck publication command uploads or promotes the local modeled data to MotherDuck for Dives. Publication MUST preserve live agent-generated plan artifacts; it MUST NOT blindly replace a namespace that stores cloud-generated trip plans unless those plans are migrated or stored outside the replaced namespace.
3. **Live agent runtime**: a Cloudflare Worker API owns live trip-planning workflow execution for the Dive. The existing Python/Google ADK planner remains a local/dev reference and evaluation harness unless a later ticket removes it.
4. **Model provider**: the Worker calls Cloudflare Workers AI through the configured OpenAI-compatible/base URL env vars and MUST use only `zai-org/glm-4.7-flash`. No silent fallback to another model is allowed.
5. **Secrets**: `MOTHERDUCK_TOKEN`, `CF_WORKERS_AI_API_KEY`, `CF_WORKERS_AI_ACCOUNT_ID`, and `CF_WORKERS_AI_MODEL_BASE_URL` MUST be read from environment-managed secrets, never from browser code, committed files, Dive source, logs, or `.10x` records.
6. **Dive integration**: the MotherDuck Dive remains a React + SQL surface. It MAY submit/poll workflow requests through the Worker, but it MUST NOT execute the agent or hold private API tokens in browser code.
7. **Access control**: workflow trigger endpoints MUST be protected by Cloudflare Access or an equivalent identity gate, and the Worker MUST also enforce bounded inputs and rate/cost guardrails.

## Alternatives considered

- **Keep Python/Google ADK as live runtime**: preserves the original MVP contract and avoids rewriting the planner, but does not satisfy the user's Cloudflare Worker ownership requirement and makes Dive-triggered product access harder without hosting a separate Python service.
- **Run dlt/SQLMesh directly against MotherDuck**: simpler for the Dive because data is already remote, but it abandons the user's explicit Quack-first local warehouse expectation and weakens local reproducibility.
- **Whole-database `CREATE OR REPLACE DATABASE databox FROM data/databox.duckdb` only**: easy snapshot upload, but unsafe if live Worker-generated trip plans are stored in the same database because publication could delete cloud-only plan history.
- **Public unauthenticated Worker demo**: easiest to call from the Dive, but exposes spend and write surfaces; rejected in favor of Cloudflare Access.
- **Browser-side model calls**: rejected because private Cloudflare and MotherDuck credentials must not be exposed to the Dive/browser.
- **Open-source/self-hosted model path**: best aligned with project principles, but explicitly superseded by the user for this agent/model layer.

## Consequences

- The Open Source First exception is narrow: it applies only to the live agent/model execution layer for this product mode. Source ingestion, SQLMesh transformations, persisted data, and Dive code should remain open and portable where possible.
- A small model-client boundary is required so a future open/self-hosted model can replace Cloudflare Workers AI without changing the Dive or data contracts.
- Cloudflare Access configuration becomes part of deployment readiness.
- The publication path must be data-loss-safe around live trip-plan artifacts.
- Deployment may require Cloudflare credentials beyond the existing Workers AI inference env vars.
