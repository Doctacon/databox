"""Analytics domain — cross-domain SQLMesh marts + Soda checks.

Analytics has no dlt ingestion and no dedicated schedule; its tables are
rebuilt as part of any upstream source run via `all_pipelines`.
"""

from datetime import timedelta

import dagster as dg

from databox.orchestration._factories import SODA_DIR, freshness_checks, soda_check

sqlmesh_asset_keys = [
    dg.AssetKey(["sqlmesh", "analytics", "fct_bird_weather_daily"]),
    dg.AssetKey(["sqlmesh", "analytics", "fct_species_weather_preferences"]),
    dg.AssetKey(["sqlmesh", "analytics", "fct_species_environment_daily"]),
    dg.AssetKey(["sqlmesh", "analytics", "platform_health"]),
]

FRESHNESS_SLAS: dict[dg.AssetKey, timedelta] = {
    dg.AssetKey(["sqlmesh", "analytics", "fct_species_environment_daily"]): timedelta(hours=48),
    dg.AssetKey(["sqlmesh", "analytics", "platform_health"]): timedelta(hours=2),
}

asset_checks: list[dg.AssetChecksDefinition] = [
    soda_check(
        dg.AssetKey(["sqlmesh", "analytics", "fct_bird_weather_daily"]),
        SODA_DIR / "contracts/analytics/fct_bird_weather_daily.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "analytics", "fct_species_weather_preferences"]),
        SODA_DIR / "contracts/analytics/fct_species_weather_preferences.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "analytics", "platform_health"]),
        SODA_DIR / "contracts/analytics/platform_health.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "analytics", "fct_species_environment_daily"]),
        SODA_DIR / "contracts/analytics/fct_species_environment_daily.yaml",
    ),
    *freshness_checks(FRESHNESS_SLAS),
]
