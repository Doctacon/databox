"""Dagster-owned manual USFWS media discovery with modeled targets."""

import typing as t
from collections.abc import Mapping, Sequence
from pathlib import Path

import dagster as dg
from databox_sources.usfws.source import usfws_source

from databox.config.settings import settings
from databox.public_media_ingest import ingest_public_usfws_media

_TARGET_CATALOG_KEY = dg.AssetKey(["sqlmesh", "rufous_public", "gbif_eod_occurrence"])
_SEARCH_RUNS_KEY = dg.AssetKey(["sqlmesh", "raw_usfws", "image_search_runs"])
_IMAGE_RECORDS_KEY = dg.AssetKey(["sqlmesh", "raw_usfws", "image_records"])
_LOAD_STATUS_KEY = dg.AssetKey(["sqlmesh", "raw_usfws", "_dlt_load_status"])


class UsfwsIngestConfig(dg.Config):
    """Manual run configuration; species targets always come from the modeled relation."""

    database_path: str = settings.database_path
    max_images_per_target: int = 500


def _build_source(
    *,
    target_species: Sequence[Mapping[str, str]] | None = None,
    max_images_per_target: int = 500,
) -> t.Any:
    """Build the source for callers that already own an explicit target snapshot."""
    return usfws_source(
        target_species=target_species,
        max_images_per_target=max_images_per_target,
    )


@dg.multi_asset(
    specs=[
        dg.AssetSpec(
            key=_SEARCH_RUNS_KEY, deps=[_TARGET_CATALOG_KEY], group_name="usfws_ingestion"
        ),
        dg.AssetSpec(
            key=_IMAGE_RECORDS_KEY, deps=[_TARGET_CATALOG_KEY], group_name="usfws_ingestion"
        ),
        dg.AssetSpec(
            key=_LOAD_STATUS_KEY,
            deps=[_SEARCH_RUNS_KEY, _IMAGE_RECORDS_KEY],
            group_name="usfws_ingestion",
        ),
    ],
    can_subset=False,
)
def usfws_dlt_assets(config: UsfwsIngestConfig) -> t.Iterator[dg.MaterializeResult[t.Any]]:
    """Derive modeled targets and materialize one complete manual USFWS snapshot."""
    result = ingest_public_usfws_media(
        Path(config.database_path),
        max_images_per_target=config.max_images_per_target,
    )
    common: dict[str, str | int] = {
        "run_id": result.run_id,
        "target_species": result.target_species,
        "completed_runs": result.completed_runs,
    }
    yield dg.MaterializeResult(asset_key=_SEARCH_RUNS_KEY, metadata=common)
    yield dg.MaterializeResult(
        asset_key=_IMAGE_RECORDS_KEY,
        metadata={**common, "raw_records": result.raw_records},
    )
    yield dg.MaterializeResult(
        asset_key=_LOAD_STATUS_KEY,
        metadata={**common, "rows_loaded": result.raw_records + result.completed_runs},
    )


assets = [usfws_dlt_assets]
dlt_asset_keys = [_SEARCH_RUNS_KEY, _IMAGE_RECORDS_KEY, _LOAD_STATUS_KEY]
sqlmesh_asset_keys: list[dg.AssetKey] = []
asset_checks: list[dg.AssetChecksDefinition] = []
ingest_job = dg.define_asset_job(
    name="usfws_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys),
    executor_def=dg.in_process_executor,
)
