"""USFWS source builder for explicit public-media snapshot ingestion.

USFWS does not have a safe repository-wide default target set.  The public
release script derives and validates its targets from the modeled publication
catalog, so this domain deliberately contributes no unconfigured Dagster asset
or job.  Registering one would expose a job that can only fail (or tempt a
caller to invent an implicit target list).
"""

import typing as t
from collections.abc import Mapping, Sequence

from databox_sources.usfws.source import usfws_source


def _build_source(
    *,
    target_species: Sequence[Mapping[str, str]] | None = None,
    max_images_per_target: int = 500,
) -> t.Any:
    """Build the source; callers own the explicit target-species snapshot."""
    return usfws_source(
        target_species=target_species,
        max_images_per_target=max_images_per_target,
    )


assets: list[t.Any] = []
dlt_asset_keys: list[t.Any] = []
sqlmesh_asset_keys: list[t.Any] = []
asset_checks: list[t.Any] = []
ingest_job = None
