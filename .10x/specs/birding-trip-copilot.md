Status: active
Created: 2026-07-08
Updated: 2026-07-09

# Birding Trip Copilot

## Purpose and scope

The Birding Trip Copilot is Databox's first agentic birding workflow. It helps a hobbyist birder plan a local outing by turning a requested place/time window into an evidence-backed target list and field plan.

This spec governs the user-visible trip-planning behavior and persisted trip-plan artifact shape. Source-specific data integration is governed by `.10x/specs/birding-agent-data-integrations.md`. The local React/API surface is governed by `.10x/specs/local-birding-trip-copilot-app.md`. Cloudflare inference is governed by `.10x/specs/cloudflare-workers-ai-local-agent.md`. DeepEval behavior is governed by `.10x/specs/birding-agent-evaluations.md`.

## Ratified MVP boundaries

- The first workflow MUST be trip planning.
- The MVP MUST NOT include stored personal sightings, life-list ingestion, user accounts, or user profiles.
- The MVP MUST use Python with Google ADK for the agent runtime.
- The local product MUST use only Cloudflare Workers AI model `@cf/zai-org/glm-4.7-flash` for model-generated agent behavior; no fallback model is allowed.
- The MVP MUST use persisted trip-plan outputs as the contract between the Python agent and the local React/API product surface.
- The MVP MUST include DeepEval tests in the first implementation slice.
- The MVP SHOULD use existing Databox eBird/weather/environmental data plus GBIF, Xeno-canto, and Open-Meteo context.

## Explicit exclusions

The MVP MUST NOT include:

- A separately user-facing species plausibility workflow.
- A separately user-facing field ID helper.
- A birding coach workflow.
- Personal life-list or historical personal sighting personalization.
- Image recognition.
- Proprietary/closed data services when a viable open/free source exists.

The planner MAY internally perform plausibility checks as part of ranking and caveat generation, but this internal behavior does not create a separate user-facing agent.

## Inputs

The trip planner MUST accept, at minimum:

- location: a user-provided place, coordinates, hotspot, or region supported by the implemented location resolver,
- date/time window: the intended outing date and approximate time window,
- duration: the intended outing duration,
- skill level: optional beginner/intermediate/advanced hint,
- constraints: optional free-text constraints such as accessible walk, avoid long drive, target waterbirds, or focus on bird calls.

If a required input is missing or ambiguous, the planner MUST ask for the smallest clarifying input needed instead of inventing a location/time.

## Agentic workflow

The planner MUST do more than directly generate prose. It MUST choose and sequence bounded tools that cover these responsibilities:

1. Resolve or normalize the requested location.
2. Retrieve recent/local bird-observation evidence from existing eBird-derived data where available.
3. Retrieve historical/occurrence/taxonomy context from modeled warehouse data, including GBIF-derived context when implemented.
4. Retrieve weather/elevation context from Open-Meteo for the requested outing window.
5. Retrieve media/call metadata from Xeno-canto-derived context when implemented.
6. Rank likely species and uncommon-but-plausible targets.
7. Produce final field-ready recommendations with evidence and caveats.
8. Persist the plan, recommended species, evidence rows, and tool trace needed for the local React/API product.

The planner MUST NOT silently skip a required evidence family. If a source is unavailable, the final plan MUST include a source-availability caveat and the persisted evidence MUST record the missing source state.

## Output behavior

A completed trip plan MUST contain:

- requested place and normalized coordinates/region where available,
- outing date/time and duration,
- weather/elevation context,
- concise field plan: arrival timing, habitat/focus areas, listening/looking strategy, and practical caveats,
- high-likelihood species list,
- uncommon-but-plausible target list,
- species-level confidence or rationale labels,
- media/call examples where available, including license/provenance metadata,
- evidence/provenance sufficient to explain why each recommended species was included,
- caveats for sparse, stale, unavailable, conflicting, or weak evidence.

The final user-facing prose SHOULD be field-ready and concise. Detailed evidence MAY be exposed through the local React app rather than repeated in full in the prose.

## Persisted artifact contract

The implementation MUST persist agent outputs in local DuckDB tables or views suitable for display through the local Python API and React app.

At minimum, persisted artifacts MUST support these logical grains:

- one row per generated trip plan,
- one row per recommended species per trip plan,
- one row per evidence item per recommended species or per trip plan,
- one row per tool call or trace step per trip plan.

The persisted artifact MUST include enough stable identifiers for the local API, React app, and evaluations to join plans, recommendations, evidence, and traces. Exact physical schema names are implementation details, but the SQL interface MUST be documented before the local app ticket is closed.

## Acceptance criteria

- A user can generate a trip plan for a supported location/time window without personal-history data.
- The agent uses bounded tools rather than a single ungrounded prompt response.
- The output includes a high-likelihood species section and an uncommon-but-plausible target section.
- The output includes weather/elevation context from Open-Meteo or an explicit source-unavailable caveat.
- The output includes GBIF/Xeno-canto-derived context where those source integrations have data, or explicit caveats where they do not.
- The output includes source/provenance evidence rather than only model prose.
- The output is persisted into queryable local DuckDB artifacts that the local Python API and React app can read.
- DeepEval tests cover at least one golden trip-planning scenario and expected tool-use behavior.
