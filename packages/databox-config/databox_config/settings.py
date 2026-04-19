"""Databox global settings loaded from environment and config files."""

from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class DataboxSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    backend: str = Field(default="local", alias="DATABOX_BACKEND")  # "local" or "motherduck"
    motherduck_token: str = Field(default="", alias="MOTHERDUCK_TOKEN")
    dlt_data_dir: str = str(PROJECT_ROOT / "pipelines" / ".dlt")
    log_level: str = "INFO"

    @computed_field
    @property
    def database_path(self) -> str:
        return "md:databox" if self.backend == "motherduck" else str(DATA_DIR / "databox.duckdb")

    @computed_field
    @property
    def raw_ebird_path(self) -> str:
        return (
            "md:raw_ebird" if self.backend == "motherduck" else str(DATA_DIR / "raw_ebird.duckdb")
        )

    @computed_field
    @property
    def raw_noaa_path(self) -> str:
        return "md:raw_noaa" if self.backend == "motherduck" else str(DATA_DIR / "raw_noaa.duckdb")

    @computed_field
    @property
    def raw_usgs_path(self) -> str:
        return "md:raw_usgs" if self.backend == "motherduck" else str(DATA_DIR / "raw_usgs.duckdb")


settings = DataboxSettings()
