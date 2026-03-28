"""Auto-discovery of pipeline source modules."""

import importlib
import logging
from pathlib import Path

from config.pipeline_config import PipelineConfig, load_all_pipeline_configs
from pipelines.base import PipelineSource

logger = logging.getLogger(__name__)

SOURCES_DIR = Path(__file__).parent / "sources"

_REGISTRY: dict[str, PipelineSource] | None = None


def _build_source(config: PipelineConfig) -> PipelineSource:
    module = importlib.import_module(config.source_module)
    factory = getattr(module, "create_pipeline", None)
    if factory is None:
        raise AttributeError(
            f"{config.source_module} must expose a create_pipeline(config) function"
        )
    source: PipelineSource = factory(config)
    return source


def get_registry(*, refresh: bool = False) -> dict[str, PipelineSource]:
    global _REGISTRY
    if _REGISTRY is not None and not refresh:
        return _REGISTRY

    configs = load_all_pipeline_configs()
    registry: dict[str, PipelineSource] = {}

    for name, config in configs.items():
        try:
            source = _build_source(config)
            registry[name] = source
            logger.info("Registered pipeline: %s", name)
        except Exception as exc:
            logger.warning("Skipping pipeline '%s': %s", name, exc)

    _REGISTRY = registry
    return registry


def get_source(name: str) -> PipelineSource:
    registry = get_registry()
    if name not in registry:
        raise KeyError(
            f"Pipeline '{name}' not found. Available: {', '.join(sorted(registry)) or '(none)'}"
        )
    return registry[name]
