"""Pipeline configuration model."""

from typing import Any

import yaml
from pydantic import BaseModel, Field

from config.settings import PROJECT_ROOT

SOURCES_DIR = PROJECT_ROOT / "sources"


class PipelineSchedule(BaseModel):
    cron: str = "0 6 * * *"
    enabled: bool = True


class QualityRule(BaseModel):
    column: str
    check: str
    threshold: float | None = None
    values: list[str] | None = None


class PipelineConfig(BaseModel):
    name: str
    source_module: str
    description: str = ""
    schedule: PipelineSchedule = Field(default_factory=PipelineSchedule)
    params: dict[str, Any] = Field(default_factory=dict)
    quality_rules: list[QualityRule] = Field(default_factory=list)
    schema_name: str = ""
    transform_project: str = ""

    def resolve_schema_name(self) -> str:
        return self.schema_name or f"raw_{self.name}"


def load_pipeline_config(name: str) -> PipelineConfig:
    config_path = SOURCES_DIR / name / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No config found for pipeline '{name}' at {config_path}")
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return PipelineConfig(name=name, **raw)


def load_all_pipeline_configs() -> dict[str, PipelineConfig]:
    configs: dict[str, PipelineConfig] = {}
    if not SOURCES_DIR.exists():
        return configs
    for source_dir in sorted(SOURCES_DIR.iterdir()):
        config_path = source_dir / "config.yaml"
        if source_dir.is_dir() and not source_dir.name.startswith("_") and config_path.exists():
            configs[source_dir.name] = load_pipeline_config(source_dir.name)
    return configs
