"""Databox global settings — single source of truth for local runtime config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
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

    quack_uri: str = Field(default="quack:localhost:9494", alias="DATABOX_QUACK_URI")
    quack_token: str = Field(default="databox_quack_token", alias="DATABOX_QUACK_TOKEN")
    quack_shared_server: bool = Field(default=False, alias="DATABOX_QUACK_SHARED_SERVER")
    quack_timeline_dir: str = Field(default="", alias="DATABOX_QUACK_TIMELINE_DIR")
    dlt_data_dir: str = Field(
        default=str(PROJECT_ROOT / "pipelines" / ".dlt"), alias="DATABOX_DLT_DATA_DIR"
    )
    log_level: str = "INFO"

    ebird_days_back: int = Field(default=30, alias="DATABOX_EBIRD_DAYS_BACK")
    noaa_days_back: int = Field(default=30, alias="DATABOX_NOAA_DAYS_BACK")
    usgs_days_back: int = Field(default=30, alias="DATABOX_USGS_DAYS_BACK")
    smoke: bool = Field(default=False, alias="DATABOX_SMOKE")

    openlineage_url: str = Field(default="", alias="OPENLINEAGE_URL")
    openlineage_namespace: str = Field(default="databox", alias="OPENLINEAGE_NAMESPACE")
    openlineage_api_key: str = Field(default="", alias="OPENLINEAGE_API_KEY")

    cf_workers_ai_api_key: SecretStr = Field(default=SecretStr(""), alias="CF_WORKERS_AI_API_KEY")
    cf_workers_ai_account_id: str = Field(default="", alias="CF_WORKERS_AI_ACCOUNT_ID", repr=False)
    cf_workers_ai_model_base_url: str = Field(
        default="", alias="CF_WORKERS_AI_MODEL_BASE_URL", repr=False
    )

    # Local generic SMTP delivery; every value is redacted and validated only by
    # the explicit alert sender/preflight, never during application startup.
    alert_smtp_enabled: SecretStr = Field(default=SecretStr(""), alias="BIRD_ALERT_SMTP_ENABLED")
    alert_smtp_security: SecretStr = Field(default=SecretStr(""), alias="BIRD_ALERT_SMTP_SECURITY")
    alert_smtp_host: SecretStr = Field(default=SecretStr(""), alias="BIRD_ALERT_SMTP_HOST")
    alert_smtp_port: SecretStr = Field(default=SecretStr(""), alias="BIRD_ALERT_SMTP_PORT")
    alert_smtp_username: SecretStr = Field(default=SecretStr(""), alias="BIRD_ALERT_SMTP_USERNAME")
    alert_smtp_password: SecretStr = Field(default=SecretStr(""), alias="BIRD_ALERT_SMTP_PASSWORD")
    alert_smtp_organizer: SecretStr = Field(default=SecretStr(""), alias="BIRD_ALERT_FROM_EMAIL")
    alert_smtp_recipient: SecretStr = Field(
        default=SecretStr(""), alias="BIRD_ALERT_RECIPIENT_EMAIL"
    )
    alert_smtp_ca_file: SecretStr = Field(default=SecretStr(""), alias="BIRD_ALERT_SMTP_CA_FILE")

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

        state_connection = DuckDBConnectionConfig(database=str(DATA_DIR / "sqlmesh_state.duckdb"))
        gateways = {
            "local": GatewayConfig(
                connection=DuckDBConnectionConfig(
                    catalogs={"databox": self.database_path},
                    extensions=[{"name": "h3", "repository": "community"}],
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
