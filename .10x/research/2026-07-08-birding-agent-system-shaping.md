Status: active
Created: 2026-07-08
Updated: 2026-07-08

# Birding agent system shaping

## Question

How should Databox turn the user's external LLM conversation into a concrete, local-first Python agentic birding application, and what source/API families appear useful for the first implementation slice?

## Sources and methods

- User-provided external LLM conversation on 2026-07-08. The conversation proposed a "Birding Trip Copilot" with trip planning, species plausibility, field ID help, and coaching agents.
- Current Databox records and source were inspected:
  - `README.md`
  - `docs/adr/0001-duckdb-as-primary-warehouse.md`
  - `docs/adr/0005-dagster-as-sole-orchestrator.md`
  - `docs/adr/0007-quack-single-file-local-ingest.md`
  - `docs/new-source.md`
  - `packages/databox-sources/databox_sources/*/config.yaml`
  - `packages/databox/databox/orchestration/definitions.py`
  - `app/main.py`
- Preliminary web research consulted current public docs/search results for:
  - eBird API terms: `https://www.birds.cornell.edu/home/ebird-api-terms-of-use/`
  - GBIF developer/API docs: `https://techdocs.gbif.org/en/openapi/` and `https://www.gbif.org/developer/summary`
  - iNaturalist API: `https://www.inaturalist.org/api`
  - Xeno-canto API/dataset references: `https://xeno-canto.org/explore/api` and GBIF dataset references
  - Google ADK workflows and multi-agent patterns: `https://adk.dev/workflows/`, `https://adk.dev/agents/workflow-agents/`
  - DeepEval tool metrics: `https://deepeval.com/docs/metrics-tool-correctness`, `https://deepeval.com/docs/metrics-tool-use`
  - Open-Meteo weather/elevation APIs: `https://open-meteo.com/`, `https://open-meteo.com/en/docs/elevation-api`

## Findings

### Existing Databox substrate

- Databox already has the local-first warehouse and orchestration substrate for the proposed app:
  - dlt source ingestion into `data/databox.duckdb` through Quack.
  - Current raw source schemas: `raw_ebird`, `raw_noaa`, `raw_usgs`, `raw_usgs_earthquakes`.
  - SQLMesh-owned CDM schema: `environmental_observations`.
  - Dagster is the sole orchestrator for dlt assets, schedules, sensors, and checks; native SQLMesh CLI owns transforms.
  - Source addition should follow `docs/new-source.md` and preserve source domains as ingestion-only.
- Existing `app/main.py` is a Streamlit data explorer, not an agent application.

### Candidate product surface from the external conversation

The strongest first product surface is a **Birding Trip Copilot**:

> Given a location, date/time window, duration, skill level, and constraints, produce an evidence-backed birding plan with likely species, plausible target birds, weather/habitat context, caveats, and citations/provenance.

The conversation also proposed later/secondary agents:

- Species plausibility agent: classify whether a reported/claimed bird is common, rare-but-plausible, or unlikely for a place/time.
- Field ID helper agent: narrow possible species from field marks, place, season, habitat, and behavior.
- Birding coach agent: generate practice lists, audio drills, and post-trip reflections.

### Candidate source/API families

- **Already present:** eBird, NOAA historical weather, USGS streamflow, USGS earthquakes. Earthquakes are likely orthogonal to birding trip planning, but may remain as existing environmental context.
- **High-value additions for first slice:**
  - GBIF occurrence data for broader biodiversity/species occurrence context and taxonomy support.
  - Xeno-canto sound metadata/media references for license-aware bird call examples.
  - Open-Meteo forecast/elevation for practical trip-planning weather and elevation context; current NOAA source is historical observation data, not a forecast tool.
- **Potential additions after MVP:**
  - iNaturalist observations for broader community naturalist sightings; useful but may overlap with GBIF and add identity/taxonomy reconciliation cost.
  - OpenStreetMap/Overpass/Nominatim or other open geospatial sources for place lookup, water proximity, trails, parks, and habitat cues.
  - Land-cover datasets for stronger habitat modeling. These are likely heavier than needed for a first agent slice.

### Agent/evaluation stack implications

- Google ADK appears suitable for a root planner agent plus tools/sub-agents. Implementation details must be verified against the exact version selected before coding.
- DeepEval has agent/tool-oriented metrics (`ToolCorrectnessMetric`, `ToolUseMetric`) that can test expected tool selection and tool-call behavior. This is a good fit for evaluating whether the planner gathers observations/weather/media before answering.

## Conclusions

- Do not start by building all four agents. The smallest useful agentic system is one **Trip Planner** workflow with a planner agent and a bounded **Species Plausibility** checker/tool/sub-agent.
- The first implementation should likely add only the data needed to make trip plans field-ready:
  - keep existing eBird + CDM tables,
  - add GBIF occurrence/taxonomy support if the user's GBIF credentials are intended for this app,
  - add Xeno-canto metadata for bird sounds/media links,
  - add Open-Meteo forecast/elevation as an online tool or dlt source depending on retention needs.
- A spec-first gate applies. This is net-new user-visible behavior, agent behavior, tool behavior, data-source semantics, evaluation behavior, and likely app/interface behavior. Focused specs should precede executable tickets.
- Current execution blockers: interface choice, first workflow scope, data-source slice, agent topology, and whether personalization/personal bird history is in or out of MVP.

## User-ratified shaping answers

Captured 2026-07-08:

- First workflow: **Trip planner**.
- First data-source slice: **GBIF + Xeno-canto + Open-Meteo**, alongside existing eBird/NOAA/USGS data.
- Personalization: **No life list** in the MVP.
- First app surface: **MotherDuck Dive**.

## Additional ratified answers

Captured 2026-07-08:

- Dive role: **persisted plans**. Python/Google ADK generates and persists plans/evidence/traces; MotherDuck Dive visualizes those persisted artifacts.
- Evaluations: **include DeepEval in the first implementation slice**.

## Resulting records

- `.10x/specs/birding-trip-copilot.md`
- `.10x/specs/birding-agent-data-integrations.md`
- `.10x/specs/superseded/birding-trip-plan-dive.md`
- `.10x/specs/birding-agent-evaluations.md`
- `.10x/tickets/done/2026-07-08-build-birding-trip-copilot.md`
