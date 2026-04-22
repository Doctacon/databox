"""Databox global settings — single source of truth for runtime config.

Every runtime configuration decision — backend selector, DuckDB paths,
MotherDuck URIs, SQLMesh gateway, Soda datasource, Dagster resources,
per-source API tokens, per-source days-back window — is declared or
derived here. Other files (SQLMesh `config.py`, Dagster `definitions.py`,
dlt sources, scripts) import from this module. Nothing else calls
`os.getenv` for these keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class DataboxSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    backend: str = Field(default="local", alias="DATABOX_BACKEND")
    motherduck_token: str = Field(default="", alias="MOTHERDUCK_TOKEN")
    dlt_data_dir: str = str(PROJECT_ROOT / "pipelines" / ".dlt")
    log_level: str = "INFO"

    # Per-source API tokens live in env via dlt's config pipeline and remain
    # read via os.getenv at call time so test monkeypatching works; migrating
    # them off .env is tracked by ticket:secrets-pluggable.
    ebird_days_back: int = Field(default=30, alias="DATABOX_EBIRD_DAYS_BACK")
    noaa_days_back: int = Field(default=30, alias="DATABOX_NOAA_DAYS_BACK")
    usgs_days_back: int = Field(default=30, alias="DATABOX_USGS_DAYS_BACK")

    smoke: bool = Field(default=False, alias="DATABOX_SMOKE")

    # OpenLineage — unset by default. When OPENLINEAGE_URL is set, Dagster
    # attaches an OpenLineage sensor at startup; it emits RunEvent / JobEvent /
    # DatasetEvent per asset materialization and asset check. Point the URL at
    # Marquez / DataHub / OpenMetadata / Atlan / Astro — every major lineage
    # catalog speaks OpenLineage. See docs/observability.md.
    openlineage_url: str = Field(default="", alias="OPENLINEAGE_URL")
    openlineage_namespace: str = Field(default="databox", alias="OPENLINEAGE_NAMESPACE")
    openlineage_api_key: str = Field(default="", alias="OPENLINEAGE_API_KEY")

    @property
    def gateway(self) -> str:
        return "motherduck" if self.backend == "motherduck" else "local"

    @property
    def database_path(self) -> str:
        return "md:databox" if self.backend == "motherduck" else str(DATA_DIR / "databox.duckdb")

    @property
    def raw_ebird_path(self) -> str:
        return (
            "md:raw_ebird" if self.backend == "motherduck" else str(DATA_DIR / "raw_ebird.duckdb")
        )

    @property
    def raw_noaa_path(self) -> str:
        return "md:raw_noaa" if self.backend == "motherduck" else str(DATA_DIR / "raw_noaa.duckdb")

    @property
    def raw_usgs_path(self) -> str:
        return "md:raw_usgs" if self.backend == "motherduck" else str(DATA_DIR / "raw_usgs.duckdb")

    @property
    def raw_usgs_earthquakes_path(self) -> str:
        return (
            "md:raw_usgs_earthquakes"
            if self.backend == "motherduck"
            else str(DATA_DIR / "raw_usgs_earthquakes.duckdb")
        )

    def days_back(self, source: str) -> int:
        return int(getattr(self, f"{source}_days_back"))

    @property
    def motherduck_database_names(self) -> list[str]:
        """All MotherDuck databases this stack expects to exist.

        Derived by introspecting `raw_*_path` properties on this class plus the
        primary `databox` database. Used by the startup auto-create routine so
        adding a new source via `new_source.py` does not require manual
        `CREATE DATABASE` in MotherDuck.
        """
        names = ["databox"]
        for attr in dir(type(self)):
            if attr.startswith("raw_") and attr.endswith("_path"):
                base = attr[len("raw_") : -len("_path")]
                names.append(f"raw_{base}")
        return names

    @property
    def soda_datasource_yaml(self) -> str:
        return f"name: databox\ntype: duckdb\nconnection:\n  database: {self.database_path}\n"

    def sqlmesh_config(self) -> Any:
        """Build a SQLMesh `Config` object from current settings.

        Imports SQLMesh lazily so importing this module does not pull in
        SQLMesh for consumers that do not need it (e.g. dlt sources).
        """
        from sqlmesh.core.config import (
            Config,
            DuckDBConnectionConfig,
            GatewayConfig,
            LinterConfig,
            ModelDefaultsConfig,
        )
        from sqlmesh.core.config.connection import MotherDuckConnectionConfig

        extensions = [{"name": "h3", "repository": "community"}]

        local_gateway = GatewayConfig(
            connection=DuckDBConnectionConfig(
                catalogs={
                    "databox": str(DATA_DIR / "databox.duckdb"),
                    "raw_ebird": str(DATA_DIR / "raw_ebird.duckdb"),
                    "raw_noaa": str(DATA_DIR / "raw_noaa.duckdb"),
                    "raw_usgs": str(DATA_DIR / "raw_usgs.duckdb"),
                    "raw_usgs_earthquakes": str(DATA_DIR / "raw_usgs_earthquakes.duckdb"),
                },
                extensions=extensions,
            )
        )

        motherduck_gateway = GatewayConfig(
            connection=MotherDuckConnectionConfig(
                token=self.motherduck_token,
                catalogs={
                    "databox": "md:databox",
                    "raw_ebird": "md:raw_ebird",
                    "raw_noaa": "md:raw_noaa",
                    "raw_usgs": "md:raw_usgs",
                    "raw_usgs_earthquakes": "md:raw_usgs_earthquakes",
                },
                extensions=extensions,
            )
        )

        return Config(
            gateways={"local": local_gateway, "motherduck": motherduck_gateway},
            default_gateway=self.gateway,
            model_defaults=ModelDefaultsConfig(dialect="duckdb", start="2025-07-25", cron="@daily"),
            linter=LinterConfig(
                enabled=True,
                rules=["ambiguousorinvalidcolumn", "invalidselectstarexpansion"],
            ),
        )


settings = DataboxSettings()
