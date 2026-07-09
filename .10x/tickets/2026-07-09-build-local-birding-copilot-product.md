Status: open
Created: 2026-07-09
Updated: 2026-07-09
Parent: None
Depends-On: None

# Build local Birding Trip Copilot product

## Aggregate outcome

Deliver a local-only Databox product with:

- one `data/databox.duckdb` warehouse/application database,
- concurrent hermetic source loading through one shared Quack server,
- local SQLMesh transformations,
- Python/Google ADK agent runtime,
- Cloudflare Workers AI inference using only `@cf/zai-org/glm-4.7-flash`,
- local React + Python API product surface,
- no active MotherDuck backend or Dive artifacts.

This is a parent plan and is not executable directly.

## Governing records

- `.10x/decisions/local-only-birding-product-architecture.md`
- `.10x/specs/local-only-databox-platform.md`
- `.10x/specs/parallel-quack-local-refresh.md`
- `.10x/specs/cloudflare-workers-ai-local-agent.md`
- `.10x/specs/local-birding-trip-copilot-app.md`
- `.10x/specs/birding-trip-copilot.md`
- `.10x/specs/birding-agent-data-integrations.md`
- `.10x/specs/birding-agent-evaluations.md`

## Child sequence

1. `.10x/tickets/2026-07-09-decommission-motherduck-platform-support.md`
2. `.10x/tickets/2026-07-09-implement-shared-quack-parallel-refresh.md`
3. `.10x/tickets/2026-07-09-integrate-cloudflare-ai-with-adk.md`
4. `.10x/tickets/2026-07-09-build-local-react-trip-planner.md`
5. `.10x/tickets/2026-07-09-verify-local-birding-product.md`

The sequence is intentional because the first four children touch overlapping configuration/runtime surfaces. Parent orchestration SHOULD avoid concurrent writers to the same worktree.

## Integration points

- Decommissioning MotherDuck establishes the final local settings contract used by later children.
- Shared Quack refresh owns source concurrency and database refresh lifecycle.
- Cloudflare integration owns model inference and planner persistence behavior.
- The local API/React app consumes planner and persisted artifact contracts.
- Final verification proves the aggregate product and records review/evidence.

## Aggregate acceptance criteria

- Every child acceptance criterion is mapped to evidence.
- A user can launch the local product, refresh data, create a trip plan, and inspect persisted results/evidence/traces.
- The browser bundle contains no Cloudflare secrets.
- No active MotherDuck/Dive path remains.
- Required shared-server Quack concurrency is proven, not inferred.
- CI, SQLMesh, DeepEval, frontend build/tests, local API tests, source-layout checks, and secret scans pass.

## Progress and notes

- 2026-07-09: User selected local React app, Python/Google ADK + Cloudflare Workers AI, repository-wide MotherDuck decommission, and required parallel Quack source loading.

## Blockers

None.
