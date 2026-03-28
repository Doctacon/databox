"""Base protocol for pipeline sources."""

from typing import Any, Protocol, runtime_checkable

from config.pipeline_config import PipelineConfig


@runtime_checkable
class PipelineSource(Protocol):
    """Interface that every data source must implement."""

    name: str
    config: PipelineConfig

    def resources(self) -> list[Any]:
        """Return the dlt resources for this source."""
        ...

    def load(self) -> Any:
        """Build and run the dlt pipeline. Returns the pipeline for inspection."""
        ...

    def validate_config(self) -> bool:
        """Return True if required env vars / credentials are present."""
        ...
