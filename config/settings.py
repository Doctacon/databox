"""Central configuration management for Databox."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseSettings, Field

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Project paths
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = project_root / "data"
    pipelines_dir: Path = project_root / "pipelines"
    transformations_dir: Path = project_root / "transformations"

    # Database
    database_url: str = Field(default="duckdb:///data/databox.db", env="DATABASE_URL")

    # DLT Configuration
    dlt_data_dir: Path = Field(default=data_dir / "dlt", env="DLT_DATA_DIR")
    dlt_pipeline_dir: Path = Field(default=pipelines_dir, env="DLT_PIPELINE_DIR")

    # SQLMesh Configuration
    sqlmesh_project_root: Path = Field(default=transformations_dir, env="SQLMESH_PROJECT_ROOT")
    sqlmesh_gateway: str = Field(default="local", env="SQLMESH_GATEWAY")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
