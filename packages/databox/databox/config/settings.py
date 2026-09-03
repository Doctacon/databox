"""Databox global settings — single source of truth for local runtime config."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ENV_FILE = Path(os.environ.get("DATABOX_ENV_FILE", PROJECT_ROOT / ".env"))


class DataboxSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    quack_uri: str = Field(default="quack:localhost:9494", alias="DATABOX_QUACK_URI")
    quack_token: str = Field(default="databox_quack_token", alias="DATABOX_QUACK_TOKEN")
    quack_shared_server: bool = Field(default=False, alias="DATABOX_QUACK_SHARED_SERVER")
    quack_timeline_dir: str = Field(default="", alias="DATABOX_QUACK_TIMELINE_DIR")
    dlt_data_dir: str = Field(
        default=str(PROJECT_ROOT / "pipelines" / ".dlt"), alias="DATABOX_DLT_DATA_DIR"
    )
    log_level: str = "INFO"

    ebird_days_back: int = Field(default=30, ge=1, le=30, alias="DATABOX_EBIRD_DAYS_BACK")
    gbif_max_records: int = Field(default=1000, ge=1, le=10_000, alias="DATABOX_GBIF_MAX_RECORDS")
    gbif_public_release: bool = Field(default=False, alias="DATABOX_GBIF_PUBLIC_RELEASE")
    noaa_days_back: int = Field(default=30, alias="DATABOX_NOAA_DAYS_BACK")
    usgs_days_back: int = Field(default=30, alias="DATABOX_USGS_DAYS_BACK")
    smoke: bool = Field(default=False, alias="DATABOX_SMOKE")

    openlineage_url: str = Field(default="", alias="OPENLINEAGE_URL")
    openlineage_namespace: str = Field(default="databox", alias="OPENLINEAGE_NAMESPACE")
    openlineage_api_key: str = Field(default="", alias="OPENLINEAGE_API_KEY")

    polaris_url: str = Field(default="http://127.0.0.1:8181", alias="DATABOX_POLARIS_URL")
    polaris_client_id: SecretStr = Field(default=SecretStr(""), alias="DATABOX_POLARIS_CLIENT_ID")
    polaris_client_secret: SecretStr = Field(
        default=SecretStr(""), alias="DATABOX_POLARIS_CLIENT_SECRET"
    )
    iceberg_catalog: str = Field(default="databox_lake", alias="DATABOX_ICEBERG_CATALOG")
    aws_s3_bucket: str = Field(default="", alias="DATABOX_AWS_S3_BUCKET", repr=False)
    aws_access_key_id: SecretStr = Field(default=SecretStr(""), alias="DATABOX_AWS_ACCESS_KEY_ID")
    aws_secret_access_key: SecretStr = Field(
        default=SecretStr(""), alias="DATABOX_AWS_SECRET_ACCESS_KEY"
    )
    aws_region: str = Field(default="us-west-1", alias="DATABOX_AWS_REGION")

    def pyiceberg_catalog(self) -> Any:
        """Return the shared client for the pre-provisioned Polaris catalog."""
        from pyiceberg.catalog.rest import RestCatalog

        client_id = self.polaris_client_id.get_secret_value()
        client_secret = self.polaris_client_secret.get_secret_value()
        if not client_id or not client_secret:
            raise ValueError("Polaris client credentials are required")
        polaris_url = self.polaris_url.rstrip("/")
        return RestCatalog(
            name="databox_iceberg",
            uri=f"{polaris_url}/api/catalog",
            warehouse=self.iceberg_catalog,
            credential=f"{client_id}:{client_secret}",
            scope="PRINCIPAL_ROLE:ALL",
            **{"oauth2-server-uri": f"{polaris_url}/api/catalog/v1/oauth/tokens"},
        )

    def attach_iceberg_to_duckdb(self, cursor: Any) -> None:
        """Attach the shared Polaris catalog to a DuckDB connection as polaris_aws."""

        def quote(value: str) -> str:
            return value.replace("'", "''")

        client_id = quote(self.polaris_client_id.get_secret_value())
        client_secret = quote(self.polaris_client_secret.get_secret_value())
        if not client_id or not client_secret:
            raise ValueError("Polaris client credentials are required")
        polaris_url = quote(self.polaris_url.rstrip("/"))
        catalog = quote(self.iceberg_catalog)
        cursor.execute("LOAD iceberg")
        cursor.execute(
            "CREATE OR REPLACE SECRET polaris_aws (TYPE ICEBERG, CLIENT_ID '"
            + client_id
            + "', CLIENT_SECRET '"
            + client_secret
            + "', OAUTH2_SERVER_URI '"
            + polaris_url
            + "/api/catalog/v1/oauth/tokens', OAUTH2_SCOPE 'PRINCIPAL_ROLE:ALL')"
        )
        cursor.execute(
            "ATTACH IF NOT EXISTS '"
            + catalog
            + "' AS polaris_aws (TYPE ICEBERG, ENDPOINT '"
            + polaris_url
            + "/api/catalog', SECRET polaris_aws)"
        )

    @property
    def gateway(self) -> str:
        return "local"

    @property
    def database_path(self) -> str:
        return str(DATA_DIR / "databox.duckdb")

    def raw_catalog_path(self, name: str) -> str:
        """Return the single local warehouse path used by every raw source."""
        return self.database_path

    def raw_dataset_name(self, name: str) -> str:
        """Return the source-specific physical schema in the local warehouse."""
        return f"raw_{name}"

    def days_back(self, source: str) -> int:
        return int(getattr(self, f"{source}_days_back"))

    @property
    def soda_datasource_yaml(self) -> str:
        return f"name: databox\ntype: duckdb\nconnection:\n  database: {self.database_path}\n"

    def sqlmesh_config(self) -> Any:
        """Build the single local SQLMesh gateway configuration."""
        from sqlmesh.core.config import (
            Config,
            DuckDBConnectionConfig,
            GatewayConfig,
            LinterConfig,
            ModelDefaultsConfig,
        )

        class PolarisDuckDBConnectionConfig(DuckDBConnectionConfig):
            @property
            def _cursor_init(self) -> Any:
                base_init = super()._cursor_init

                def init(cursor: Any) -> None:
                    if base_init:
                        base_init(cursor)
                    self_settings.attach_iceberg_to_duckdb(cursor)

                return init

        self_settings = self
        state_connection = DuckDBConnectionConfig(database=str(DATA_DIR / "sqlmesh_state.duckdb"))
        gateways = {
            "local": GatewayConfig(
                connection=PolarisDuckDBConnectionConfig(
                    catalogs={"databox": self.database_path},
                    extensions=[{"name": "h3", "repository": "community"}, "iceberg"],
                ),
                state_connection=state_connection,
            )
        }
        return Config(
            gateways=gateways,
            default_gateway="local",
            model_defaults=ModelDefaultsConfig(dialect="duckdb", start="2025-07-25", cron="@daily"),
            linter=LinterConfig(
                enabled=True,
                rules=["ambiguousorinvalidcolumn", "invalidselectstarexpansion"],
            ),
        )


settings = DataboxSettings()
