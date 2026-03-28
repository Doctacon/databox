"""Databox global settings loaded from environment and config files."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "databox.db"


class DataboxSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"duckdb:///{DATABASE_PATH}"
    dlt_data_dir: str = str(PROJECT_ROOT / "pipelines" / ".dlt")
    log_level: str = "INFO"

    @property
    def database_path(self) -> Path:
        url = self.database_url
        if url.startswith("duckdb:///"):
            return Path(url.removeprefix("duckdb:///"))
        return DATABASE_PATH


settings = DataboxSettings()
