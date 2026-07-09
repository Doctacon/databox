Status: done
Created: 2026-07-09
Updated: 2026-07-09

# MotherDuck + Cloudflare live product research

## Question

What current, supportable architecture can publish the local Quack warehouse to MotherDuck, expose a saved Dive, and let an authenticated product user trigger a Cloudflare Workers AI birding workflow without browser-side secrets?

## Sources and methods

Inspected project records/source:

- `.10x/specs/birding-trip-copilot.md`
- `.10x/specs/superseded/birding-trip-plan-dive.md`
- `.10x/specs/birding-agent-data-integrations.md`
- `packages/databox/databox/destinations/quack.py`
- `packages/databox/databox/agents/birding_trip_planner.py`
- `dives/birding-trip-plan/`
- `.dive-preview/`
- `Taskfile.yaml`
- `/Users/crlough/.agents/skills/motherduck-create-dive/SKILL.md`
- `/Users/crlough/.agents/skills/motherduck-create-dive/references/DIVE_DESIGN_GUIDE.md`
- `/Users/crlough/.agents/skills/motherduck-load-data/SKILL.md`
- `/Users/crlough/.agents/skills/motherduck-load-data/references/INGESTION_PATTERNS.md`
- `/Users/crlough/.agents/skills/motherduck-connect/SKILL.md`
- `/Users/crlough/.agents/skills/motherduck-connect/references/CONNECTION_GUIDE.md`
- `/Users/crlough/.agents/skills/motherduck-build-cfa-app/SKILL.md`

Consulted current official sources on 2026-07-09:

- Cloudflare Workers AI OpenAI compatibility: https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/
- Cloudflare Workers AI bindings: https://developers.cloudflare.com/workers-ai/configuration/bindings/
- Cloudflare model page for GLM 4.7 Flash: https://developers.cloudflare.com/workers-ai/models/glm-4.7-flash/
- Cloudflare Access/AI wrapper guidance: https://developers.cloudflare.com/cloudflare-one/tutorials/ai-wrapper-tenant-control/
- MotherDuck loading a DuckDB database: https://motherduck.com/docs/key-tasks/loading-data-into-motherduck/loading-duckdb-database/
- MotherDuck `CREATE DATABASE`: https://motherduck.com/docs/sql-reference/motherduck-sql-reference/create-database/
- MotherDuck Dive creation/update and embedding docs under https://motherduck.com/docs/key-tasks/ai-and-motherduck/dives/ and https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/dives/

Attempted read-only MotherDuck discovery with the configured `.env` token. Connection reached MotherDuck but authentication failed because the JWT is expired. No MotherDuck state was changed.

## Findings

### Cloudflare model identifier

Cloudflare's official Workers AI identifier is `@cf/zai-org/glm-4.7-flash`. The user's requested shorthand `zai-org/glm-4.7-flash` therefore needs to be implemented as that official provider-qualified identifier unless the configured base URL explicitly expects the unprefixed path.

The model supports text generation and tool calling according to Cloudflare's current model documentation. No model fallback is necessary or desirable for this contract.

### Worker inference path

For code running inside a Cloudflare Worker, Cloudflare's native AI binding (`env.AI.run`) is the lowest-complexity path. The user also supplied an API key, account ID, and model base URL, which can support an OpenAI-compatible HTTP client. The implementation should pick one path rather than mix both. Native binding is preferable for a deployed Worker; an OpenAI-compatible client boundary may be useful for local tests and portability.

### Local DuckDB publication

MotherDuck supports uploading an existing local DuckDB database through a native DuckDB client using `CREATE DATABASE ... FROM` the current database, an attached database, or a file path. Whole-database replace/overwrite is unsuitable when cloud-only trip-plan writes live in the replaced database, because the publish could delete those artifacts.

The safe shape is to separate rebuildable warehouse data from cloud-generated app state, or publish table/schema slices rather than replacing the app-state namespace.

### Dive/product boundary

MotherDuck Dives are React + SQL artifacts optimized for read-only analytics. MotherDuck skill guidance explicitly recommends escalating to a 3-tier customer-facing app when the product needs custom writes, backend authorization, and non-Dive API routes.

Best practice for this requirement is therefore a small Cloudflare-hosted product shell behind Access that:

- submits trip-plan requests to the Worker,
- displays status/results,
- embeds or links to the saved MotherDuck Dive for live persisted analytics.

Trying to make the Dive itself a write-capable application by calling an external Worker directly is less supported and blurs the read-only security boundary.

### Deployment prerequisites

The current `.env` contains non-empty values for:

- `MOTHERDUCK_TOKEN`
- `CF_WORKERS_AI_API_KEY`
- `CF_WORKERS_AI_ACCOUNT_ID`
- `CF_WORKERS_AI_MODEL_BASE_URL`

It does not contain `CLOUDFLARE_API_TOKEN` or `CLOUDFLARE_ACCOUNT_ID`. The Workers AI account ID may be the same account used for deployment, but that cannot be assumed. Wrangler may already be interactively authenticated, but that has not been established.

The configured `MOTHERDUCK_TOKEN` is expired as of the read-only discovery attempt.

## Conclusions

Recommended architecture:

1. One local Quack server owns `data/databox.duckdb`; independent dlt clients load source-specific schemas concurrently only after safe shared-server behavior is proven.
2. SQLMesh materializes local modeled data.
3. Publish rebuildable modeled data to MotherDuck while keeping cloud-generated trip-plan state in a separate, preserved database/namespace.
4. Deploy a Cloudflare Worker + thin product shell behind Cloudflare Access.
5. Use only Cloudflare's official `@cf/zai-org/glm-4.7-flash` model identifier.
6. Keep the saved MotherDuck Dive read-only and embed/link it from the product shell rather than exposing write/API secrets in Dive code.

## Subsequent direction

After reviewing the deployment, synchronization, and Dive write-boundary implications, the user rejected MotherDuck and deployment in favor of `.10x/decisions/local-only-birding-product-architecture.md`. The cloud findings remain useful rationale, but they are not active implementation direction.

## Limits and blockers

- Live MotherDuck schema/Dive discovery is blocked until `MOTHERDUCK_TOKEN` is refreshed.
- Worker deployment and Access setup cannot be assumed without authenticated Wrangler or deployment credentials and a selected route/domain.
- Embedded Dives require appropriate MotherDuck plan access; this has not yet been verified.
- Safe true-parallel Quack loading needs an executable validation because the current code starts/stops a Quack server per hermetic source and temporarily exposes source-specific dlt metadata views in `main`.
