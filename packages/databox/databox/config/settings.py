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

from databox.config.sources import SOURCES

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

    def raw_catalog_path(self, name: str) -> str:
        """DuckDB connection string for the raw catalog of `name`.

        Resolves to `md:raw_<name>` under MotherDuck and the on-disk
        `data/raw_<name>.duckdb` file under local mode. Callers pass the source
        name from the registry (`databox.config.sources.SOURCES`); this is the
        only place the backend branch lives for raw catalog paths.
        """
        if self.backend == "motherduck":
            return f"md:raw_{name}"
        return str(DATA_DIR / f"raw_{name}.duckdb")

    def days_back(self, source: str) -> int:
        return int(getattr(self, f"{source}_days_back"))

    @property
    def motherduck_database_names(self) -> list[str]:
        """All MotherDuck databases this stack expects to exist.

        Derived from the source registry plus the primary `databox` database.
        The startup auto-create routine consumes this so adding a source via
        `new_source.py` does not require manual `CREATE DATABASE` in MotherDuck.
        """
        return ["databox", *(src.raw_catalog for src in SOURCES)]

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

        local_catalogs = {"databox": str(DATA_DIR / "databox.duckdb")} | {
            src.raw_catalog: str(DATA_DIR / f"{src.raw_catalog}.duckdb") for src in SOURCES
        }
        motherduck_catalogs = {"databox": "md:databox"} | {
            src.raw_catalog: f"md:{src.raw_catalog}" for src in SOURCES
        }

        local_gateway = GatewayConfig(
            connection=DuckDBConnectionConfig(catalogs=local_catalogs, extensions=extensions)
        )

        motherduck_gateway = GatewayConfig(
            connection=MotherDuckConnectionConfig(
                token=self.motherduck_token,
                catalogs=motherduck_catalogs,
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
