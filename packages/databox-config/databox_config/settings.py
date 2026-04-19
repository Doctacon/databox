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

    database_path: str = str(DATA_DIR / "databox.duckdb")
    raw_ebird_path: str = str(DATA_DIR / "raw_ebird.duckdb")
    raw_noaa_path: str = str(DATA_DIR / "raw_noaa.duckdb")
    raw_usgs_path: str = str(DATA_DIR / "raw_usgs.duckdb")
    dlt_data_dir: str = str(PROJECT_ROOT / "pipelines" / ".dlt")
    log_level: str = "INFO"


settings = DataboxSettings()
