Status: cancelled
Created: 2026-07-09
Updated: 2026-07-09

# Shape live MotherDuck + Cloudflare agentic product

Cancelled after the user rejected deployment and MotherDuck. Replacement owner: `.10x/tickets/done/2026-07-09-build-local-birding-copilot-product.md`.

## Scope

Shape the product path that turns the current local Birding Trip Copilot MVP into a live product surface where:

- dlt sources load into the single local `data/databox.duckdb` file through Quack,
- the queryable product dataset is available to MotherDuck Dives,
- the Birding Trip Copilot Dive is saved/spun up in MotherDuck,
- the Dive can access an agentic workflow without browser-side secrets,
- the agent/model layer uses the user's Cloudflare Workers AI account and only `zai-org/glm-4.7-flash`.

## Current inspected state

- `.10x/specs/birding-trip-copilot.md` currently says the MVP MUST use Python with Google ADK for the agent runtime.
- `.10x/specs/superseded/birding-trip-plan-dive.md` currently says the Dive visualizes persisted trip-plan artifacts and is not the agent runtime itself.
- Local source ingest currently uses Quack-backed `data/databox.duckdb` and physical `raw_<source>` schemas.
- MotherDuck is currently an alternate backend/publish target, not an automatic attachment of the local DuckDB file.
- `dives/birding-trip-plan/` contains the Dive-as-code artifact; `.dive-preview/` contains a local Vite preview scaffold.
- MotherDuck skill guidance says a Dive should keep secrets out of the browser and use backend-created sessions/endpoints when live product behavior is needed.

## Progress and notes

- 2026-07-09: User initially ratified Cloudflare Worker ownership, MotherDuck snapshot publication, and Cloudflare Access.
- 2026-07-09: Research found the write-capable workflow would require a separate product shell or equivalent three-tier boundary rather than treating a Dive as the write-capable runtime.
- 2026-07-09: User stepped back from deployment and MotherDuck. New direction: keep the product local on the generated DuckDB database; Cloudflare may remain only as the model-inference service. The earlier live MotherDuck/Worker direction must be superseded once the exact local runtime/UI and removal scope are confirmed.

## Blockers

- The Cloudflare Workers AI requirement conflicts with the project's Open Source First rule unless the user explicitly supersedes that rule for this workstream and the decision records the rationale and exit path.
- The Cloudflare Workers AI requirement may supersede the active Python/Google ADK runtime contract; ownership of the live agent runtime must be explicit.
- MotherDuck publication semantics must be ratified: local Quack snapshot upload/publish versus running ingestion/transforms directly against MotherDuck.
- Dive-triggered workflow access needs an authentication/guardrail contract that keeps `MOTHERDUCK_TOKEN`, `CF_WORKERS_AI_API_KEY`, and any write credentials out of browser code.
- True parallel Quack ingest across hermetic sources must be validated because existing Quack metadata-view handling was designed for one source job at a time.

## Acceptance criteria for unblocking

- User confirms whether Cloudflare Workers AI supersedes Open Source First for this agent/model layer.
- User confirms the live agent runtime owner and the role, if any, of the existing Python/Google ADK runtime.
- User confirms the MotherDuck publication path.
- User confirms who can trigger agent workflows from the Dive and which guardrails are required.
- After those decisions, create/update focused active specs, decisions, and bounded executable child tickets before implementation.
