"""Cross-domain SQLMesh assets and Soda checks.

The CDM workflow now materializes the environmental-observations model layer in
SQLMesh. dlt source domains own ingestion only; this module owns cross-source
SQLMesh assets plus operational platform health.
"""

import dagster as dg

from databox.orchestration._factories import SODA_DIR, soda_check

_CDM_SCHEMA = "environmental_observations"
_CDM_MODELS = [
    "dim_species",
    "dim_bird_hotspot",
    "dim_weather_station",
    "dim_streamgage_site",
    "fact_bird_observation",
    "fact_region_daily_stats",
    "fact_weather_observation",
    "fact_streamflow_observation",
    "fact_earthquake_event",
]

_BIRDING_AGENT_SCHEMA = "birding_agent"
_BIRDING_AGENT_MODELS = [
    "species_lookup",
    "recent_observation_evidence",
    "gbif_occurrence_evidence",
    "xeno_canto_media_evidence",
]

sqlmesh_asset_keys = [
    *(dg.AssetKey(["sqlmesh", _CDM_SCHEMA, model]) for model in _CDM_MODELS),
    *(dg.AssetKey(["sqlmesh", _BIRDING_AGENT_SCHEMA, model]) for model in _BIRDING_AGENT_MODELS),
    dg.AssetKey(["sqlmesh", "analytics", "platform_health"]),
]

asset_checks: list[dg.AssetChecksDefinition] = [
    *(
        soda_check(
            dg.AssetKey(["sqlmesh", _CDM_SCHEMA, model]),
            SODA_DIR / f"contracts/{_CDM_SCHEMA}/{model}.yaml",
        )
        for model in _CDM_MODELS
    ),
    *(
        soda_check(
            dg.AssetKey(["sqlmesh", _BIRDING_AGENT_SCHEMA, model]),
            SODA_DIR / f"contracts/{_BIRDING_AGENT_SCHEMA}/{model}.yaml",
        )
        for model in _BIRDING_AGENT_MODELS
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "analytics", "platform_health"]),
        SODA_DIR / "contracts/analytics/platform_health.yaml",
    ),
]
