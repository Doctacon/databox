"""Base protocol for pipeline sources."""

from typing import Any, Protocol, runtime_checkable

from databox_config.pipeline_config import PipelineConfig


@runtime_checkable
class PipelineSource(Protocol):
    """Interface that every data source must implement."""

    name: str
    config: PipelineConfig

    def resources(self) -> list[Any]:
        """Return the dlt resources for this source."""
        ...

    def load(self, smoke: bool = False) -> Any:
        """Build and run the dlt pipeline. smoke=True fetches minimal data for verification."""
        ...

    def validate_config(self) -> bool:
        """Return True if required env vars / credentials are present."""
        ...
