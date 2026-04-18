"""Databox global settings loaded from environment and config files."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class DataboxSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://databox:databox@localhost:5432/databox"
    dlt_data_dir: str = str(PROJECT_ROOT / "pipelines" / ".dlt")
    log_level: str = "INFO"


settings = DataboxSettings()
