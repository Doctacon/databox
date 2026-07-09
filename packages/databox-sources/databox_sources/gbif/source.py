"""GBIF occurrence source pipeline using dlt.

Data: GBIF occurrence search for birds (Aves) in the configured geography.
No API key is required for the occurrence search endpoint used here.

API: https://api.gbif.org/v1/occurrence/search
Docs: https://techdocs.gbif.org/en/openapi/v1/occurrence#/Searching%20occurrences/searchOccurrence
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import dlt
import pendulum
from databox.config.pipeline_config import PipelineConfig
from databox.config.settings import settings
from databox.destinations import dlt_destination, dlt_pipeline, prepare_dlt_source
from dlt.sources.helpers import requests as dlt_requests

from databox_sources._logging import get_logger

log = get_logger("databox_sources.gbif")

GBIF_API_BASE = "https://api.gbif.org/v1"
GBIF_OCCURRENCE_SEARCH = f"{GBIF_API_BASE}/occurrence/search"
GBIF_AVES_TAXON_KEY = 212
GBIF_PAGE_LIMIT = 300

_OCCURRENCE_COLUMNS: Any = {
    "key": {"data_type": "bigint"},
    "gbif_id": {"data_type": "text"},
    "occurrence_id": {"data_type": "text"},
    "dataset_key": {"data_type": "text"},
    "publishing_org_key": {"data_type": "text"},
    "installation_key": {"data_type": "text"},
    "hosting_organization_key": {"data_type": "text"},
    "protocol": {"data_type": "text"},
    "publishing_country": {"data_type": "text"},
    "scientific_name": {"data_type": "text"},
    "accepted_scientific_name": {"data_type": "text"},
    "vernacular_name": {"data_type": "text"},
    "kingdom": {"data_type": "text"},
    "phylum": {"data_type": "text"},
    "class_name": {"data_type": "text"},
    "order_name": {"data_type": "text"},
    "family": {"data_type": "text"},
    "genus": {"data_type": "text"},
    "species": {"data_type": "text"},
    "generic_name": {"data_type": "text"},
    "specific_epithet": {"data_type": "text"},
    "taxon_rank": {"data_type": "text"},
    "taxon_key": {"data_type": "bigint"},
    "accepted_taxon_key": {"data_type": "bigint"},
    "kingdom_key": {"data_type": "bigint"},
    "phylum_key": {"data_type": "bigint"},
    "class_key": {"data_type": "bigint"},
    "order_key": {"data_type": "bigint"},
    "family_key": {"data_type": "bigint"},
    "genus_key": {"data_type": "bigint"},
    "species_key": {"data_type": "bigint"},
    "decimal_latitude": {"data_type": "double"},
    "decimal_longitude": {"data_type": "double"},
    "coordinate_uncertainty_in_meters": {"data_type": "double"},
    "country": {"data_type": "text"},
    "country_code": {"data_type": "text"},
    "state_province": {"data_type": "text"},
    "locality": {"data_type": "text"},
    "event_date": {"data_type": "text"},
    "year": {"data_type": "bigint"},
    "month": {"data_type": "bigint"},
    "day": {"data_type": "bigint"},
    "basis_of_record": {"data_type": "text"},
    "occurrence_status": {"data_type": "text"},
    "establishment_means": {"data_type": "text"},
    "record_number": {"data_type": "text"},
    "recorded_by": {"data_type": "text"},
    "identified_by": {"data_type": "text"},
    "institution_code": {"data_type": "text"},
    "collection_code": {"data_type": "text"},
    "catalog_number": {"data_type": "text"},
    "license": {"data_type": "text"},
    "references": {"data_type": "text"},
    "last_interpreted": {"data_type": "text"},
    "last_crawled": {"data_type": "text"},
    "last_parsed": {"data_type": "text"},
    "_source_url": {"data_type": "text"},
    "_query_country_code": {"data_type": "text"},
    "_query_state_province": {"data_type": "text"},
    "_query_taxon_key": {"data_type": "bigint"},
    "_loaded_at": {"data_type": "timestamp"},
}


def _string_or_none(value: Any) -> str | None:
    """Return a stable scalar string for GBIF fields that may be arrays."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item is not None) or None
    return str(value)


def process_occurrence(
    record: dict[str, Any],
    *,
    country_code: str,
    state_province: str | None,
    taxon_key: int,
    loaded_at: str,
) -> dict[str, Any]:
    """Flatten one GBIF occurrence result into the raw table contract."""
    return {
        "key": record.get("key"),
        "gbif_id": _string_or_none(record.get("gbifID")),
        "occurrence_id": _string_or_none(record.get("occurrenceID")),
        "dataset_key": _string_or_none(record.get("datasetKey")),
        "publishing_org_key": _string_or_none(record.get("publishingOrgKey")),
        "installation_key": _string_or_none(record.get("installationKey")),
        "hosting_organization_key": _string_or_none(record.get("hostingOrganizationKey")),
        "protocol": _string_or_none(record.get("protocol")),
        "publishing_country": _string_or_none(record.get("publishingCountry")),
        "scientific_name": _string_or_none(record.get("scientificName")),
        "accepted_scientific_name": _string_or_none(record.get("acceptedScientificName")),
        "vernacular_name": _string_or_none(record.get("vernacularName")),
        "kingdom": _string_or_none(record.get("kingdom")),
        "phylum": _string_or_none(record.get("phylum")),
        "class_name": _string_or_none(record.get("class")),
        "order_name": _string_or_none(record.get("order")),
        "family": _string_or_none(record.get("family")),
        "genus": _string_or_none(record.get("genus")),
        "species": _string_or_none(record.get("species")),
        "generic_name": _string_or_none(record.get("genericName")),
        "specific_epithet": _string_or_none(record.get("specificEpithet")),
        "taxon_rank": _string_or_none(record.get("taxonRank")),
        "taxon_key": record.get("taxonKey"),
        "accepted_taxon_key": record.get("acceptedTaxonKey"),
        "kingdom_key": record.get("kingdomKey"),
        "phylum_key": record.get("phylumKey"),
        "class_key": record.get("classKey"),
        "order_key": record.get("orderKey"),
        "family_key": record.get("familyKey"),
        "genus_key": record.get("genusKey"),
        "species_key": record.get("speciesKey"),
        "decimal_latitude": record.get("decimalLatitude"),
        "decimal_longitude": record.get("decimalLongitude"),
        "coordinate_uncertainty_in_meters": record.get("coordinateUncertaintyInMeters"),
        "country": _string_or_none(record.get("country")),
        "country_code": _string_or_none(record.get("countryCode")),
        "state_province": _string_or_none(record.get("stateProvince")),
        "locality": _string_or_none(record.get("locality")),
        "event_date": _string_or_none(record.get("eventDate")),
        "year": record.get("year"),
        "month": record.get("month"),
        "day": record.get("day"),
        "basis_of_record": _string_or_none(record.get("basisOfRecord")),
        "occurrence_status": _string_or_none(record.get("occurrenceStatus")),
        "establishment_means": _string_or_none(record.get("establishmentMeans")),
        "record_number": _string_or_none(record.get("recordNumber")),
        "recorded_by": _string_or_none(record.get("recordedBy")),
        "identified_by": _string_or_none(record.get("identifiedBy")),
        "institution_code": _string_or_none(record.get("institutionCode")),
        "collection_code": _string_or_none(record.get("collectionCode")),
        "catalog_number": _string_or_none(record.get("catalogNumber")),
        "license": _string_or_none(record.get("license")),
        "references": _string_or_none(record.get("references")),
        "last_interpreted": _string_or_none(record.get("lastInterpreted")),
        "last_crawled": _string_or_none(record.get("lastCrawled")),
        "last_parsed": _string_or_none(record.get("lastParsed")),
        "_source_url": GBIF_OCCURRENCE_SEARCH,
        "_query_country_code": country_code,
        "_query_state_province": state_province,
        "_query_taxon_key": taxon_key,
        "_loaded_at": loaded_at,
    }


def _occurrence_params(
    *,
    country_code: str,
    state_province: str | None,
    taxon_key: int,
    has_coordinate: bool,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "classKey": taxon_key,
        "country": country_code,
        "hasCoordinate": str(has_coordinate).lower(),
    }
    if state_province:
        params["stateProvince"] = state_province
    return params


@dlt.source
def gbif_source(
    country_code: str = "US",
    state_province: str | None = "Arizona",
    taxon_key: int = GBIF_AVES_TAXON_KEY,
    max_records: int = 1000,
    has_coordinate: bool = True,
) -> Any:
    """GBIF bird occurrence source."""
    loaded_at = pendulum.now().isoformat()

    @dlt.resource(
        primary_key="key",
        write_disposition="merge",
        columns=_OCCURRENCE_COLUMNS,
    )
    def occurrences() -> Iterator[dict[str, Any]]:
        if max_records <= 0:
            return

        yielded = 0
        offset = 0
        base_params = _occurrence_params(
            country_code=country_code,
            state_province=state_province,
            taxon_key=taxon_key,
            has_coordinate=has_coordinate,
        )

        while yielded < max_records:
            limit = min(GBIF_PAGE_LIMIT, max_records - yielded)
            params = {**base_params, "limit": limit, "offset": offset}
            response = dlt_requests.get(
                GBIF_OCCURRENCE_SEARCH,
                headers={"Accept": "application/json"},
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", [])
            if not results:
                break

            for record in results:
                row = process_occurrence(
                    record,
                    country_code=country_code,
                    state_province=state_province,
                    taxon_key=taxon_key,
                    loaded_at=loaded_at,
                )
                if row["key"] is not None:
                    yield row
                    yielded += 1
                    if yielded >= max_records:
                        break

            log.info("occurrences_page_fetched", count=len(results), offset=offset)
            if payload.get("endOfRecords") or len(results) < limit:
                break
            offset += len(results)

    return [occurrences]


class GbifPipelineSource:
    """GBIF pipeline source implementing the PipelineSource protocol."""

    def __init__(self, config: PipelineConfig) -> None:
        self.name = config.name
        self.config = config
        self._country_code = config.params.get("country_code", "US")
        self._state_province = config.params.get("state_province", "Arizona")
        self._taxon_key = int(config.params.get("taxon_key", GBIF_AVES_TAXON_KEY))
        self._max_records = int(config.params.get("max_records", 1000))
        self._has_coordinate = bool(config.params.get("has_coordinate", True))

    def _source(self) -> Any:
        return gbif_source(
            country_code=self._country_code,
            state_province=self._state_province,
            taxon_key=self._taxon_key,
            max_records=self._max_records,
            has_coordinate=self._has_coordinate,
        )

    def resources(self) -> list[Any]:
        source = self._source()
        return list(source.resources.values())

    def load(self, smoke: bool = False) -> Any:
        pipeline = dlt_pipeline(
            pipeline_name=f"{self.name}_api",
            destination=dlt_destination(settings.raw_catalog_path("gbif")),
            dataset_name=settings.raw_dataset_name("gbif"),
            pipelines_dir=settings.dlt_data_dir,
            progress="log",
        )
        source = self._source()
        if smoke:
            source.add_limit(max_items=5)
        source = prepare_dlt_source(source)

        run_log = log.bind(
            pipeline=pipeline.pipeline_name,
            source="gbif",
            schema=self.config.resolve_schema_name(),
            country_code=self._country_code,
            state_province=self._state_province,
            taxon_key=self._taxon_key,
            smoke=smoke,
        )
        started = pendulum.now()
        run_log.info("pipeline_start")
        info = pipeline.run(source)
        duration_ms = int((pendulum.now() - started).total_seconds() * 1000)
        run_log.info(
            "pipeline_complete",
            load_id=info.loads_ids[-1] if info.loads_ids else None,
            duration_ms=duration_ms,
            has_failed_jobs=info.has_failed_jobs,
        )
        return pipeline

    def validate_config(self) -> bool:
        return True


def create_pipeline(config: PipelineConfig) -> GbifPipelineSource:
    return GbifPipelineSource(config)
