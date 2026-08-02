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
from dlt.sources.helpers import requests as dlt_requests

from databox_sources._logging import get_logger

log = get_logger("databox_sources.gbif")

GBIF_API_BASE = "https://api.gbif.org/v1"
GBIF_OCCURRENCE_SEARCH = f"{GBIF_API_BASE}/occurrence/search"
GBIF_AVES_TAXON_KEY = 212
GBIF_PAGE_LIMIT = 300
GBIF_SEARCH_RECORD_CAP = 10_000
GBIF_REQUEST_TIMEOUT_SECONDS = 30
GBIF_RUFOUS_TAXON_KEY = 2476855
GBIF_RUFOUS_RESERVE = 300
GBIF_EBIRD_EOD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
GBIF_EBIRD_EOD_DATASET_TITLE = "EOD – eBird Observation Dataset"
GBIF_EBIRD_EOD_DATASET_PUBLISHER = "Cornell Lab of Ornithology"
GBIF_EBIRD_EOD_DATASET_DOI = "10.15468/aomfnb"
GBIF_EBIRD_EOD_DATASET_URL = f"https://www.gbif.org/dataset/{GBIF_EBIRD_EOD_DATASET_KEY}"
GBIF_EBIRD_EOD_DATASET_LICENSE = "https://creativecommons.org/licenses/by/4.0/"
GBIF_EBIRD_EOD_DATASET_CITATION = (
    "Imani J, Audette C, Auer T, Barker S, Barry J, Charnoky M, Crowley C, Curtis J, "
    "Davies I, Davis C, Diaz R, Feinberg A, Fink D, Ganger J, Garrett J, Gerbracht J, "
    "Hanks C, Hayes M, Hochachka W, Iliff M, Jordan A, Ligocki S, Long T, Morris W, "
    "Morrow S, Oldham L, Padilla Obregon F, Robinson O, Rodewald A, Ruiz-Gutierrez V, "
    "Schloss M, Smith A, Smith J, Stillman A, Stokowski M, Strimas-Mackey M, Sullivan B, "
    "Tedeschi A, Weber D, Wolf H, Wood C (2025). EOD – eBird Observation Dataset. "
    "Cornell Lab of Ornithology. Occurrence dataset https://doi.org/10.15468/aomfnb"
)

_OCCURRENCE_COLUMNS: Any = {
    "key": {"data_type": "bigint"},
    "gbif_id": {"data_type": "text"},
    "occurrence_id": {"data_type": "text"},
    "dataset_key": {"data_type": "text"},
    "dataset_title": {"data_type": "text"},
    "dataset_publisher": {"data_type": "text"},
    "dataset_citation": {"data_type": "text"},
    "dataset_doi": {"data_type": "text"},
    "dataset_source_url": {"data_type": "text"},
    "dataset_license": {"data_type": "text"},
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
    "_query_dataset_key": {"data_type": "text"},
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


def _dataset_metadata(dataset_key: str | None, loaded_at: str) -> dict[str, str | None]:
    """Return stable dataset attribution for a known GBIF dataset.

    Occurrence search results expose the dataset UUID but do not consistently
    include a human-readable publisher or citation. The EOD constants mirror
    GBIF's registered dataset record and make those values explicit in the raw
    contract instead of treating observer names as dataset attribution.
    """
    if dataset_key != GBIF_EBIRD_EOD_DATASET_KEY:
        return {
            "dataset_title": None,
            "dataset_publisher": None,
            "dataset_citation": None,
            "dataset_doi": None,
            "dataset_source_url": (
                f"https://www.gbif.org/dataset/{dataset_key}" if dataset_key else None
            ),
            "dataset_license": None,
        }
    access_date = loaded_at[:10]
    return {
        "dataset_title": GBIF_EBIRD_EOD_DATASET_TITLE,
        "dataset_publisher": GBIF_EBIRD_EOD_DATASET_PUBLISHER,
        "dataset_citation": (
            f"{GBIF_EBIRD_EOD_DATASET_CITATION} accessed via GBIF.org on {access_date}."
        ),
        "dataset_doi": GBIF_EBIRD_EOD_DATASET_DOI,
        "dataset_source_url": GBIF_EBIRD_EOD_DATASET_URL,
        "dataset_license": GBIF_EBIRD_EOD_DATASET_LICENSE,
    }


def process_occurrence(
    record: dict[str, Any],
    *,
    country_code: str,
    state_province: str | None,
    taxon_key: int,
    dataset_key: str | None,
    loaded_at: str,
) -> dict[str, Any]:
    """Flatten one GBIF occurrence result into the raw table contract."""
    resolved_dataset_key = _string_or_none(record.get("datasetKey")) or dataset_key
    dataset_metadata = _dataset_metadata(resolved_dataset_key, loaded_at)
    return {
        "key": record.get("key"),
        "gbif_id": _string_or_none(record.get("gbifID")),
        "occurrence_id": _string_or_none(record.get("occurrenceID")),
        "dataset_key": resolved_dataset_key,
        "dataset_title": (
            _string_or_none(record.get("datasetTitle")) or dataset_metadata["dataset_title"]
        ),
        "dataset_publisher": (
            _string_or_none(record.get("publishingOrganizationTitle"))
            or dataset_metadata["dataset_publisher"]
        ),
        "dataset_citation": dataset_metadata["dataset_citation"],
        "dataset_doi": dataset_metadata["dataset_doi"],
        "dataset_source_url": dataset_metadata["dataset_source_url"],
        "dataset_license": dataset_metadata["dataset_license"],
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
        "_query_dataset_key": dataset_key,
        "_loaded_at": loaded_at,
    }


def _occurrence_params(
    *,
    country_code: str,
    state_province: str | None,
    taxon_key: int,
    dataset_key: str | None,
    has_coordinate: bool,
    license_code: str | None,
    occurrence_status: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "classKey": taxon_key,
        "country": country_code,
        "hasCoordinate": str(has_coordinate).lower(),
    }
    if state_province:
        params["stateProvince"] = state_province
    if dataset_key:
        params["datasetKey"] = dataset_key
    if license_code:
        params["license"] = license_code
    if occurrence_status:
        params["occurrenceStatus"] = occurrence_status
    return params


@dlt.source
def gbif_source(
    country_code: str = "US",
    state_province: str | None = "Arizona",
    taxon_key: int = GBIF_AVES_TAXON_KEY,
    dataset_key: str | None = None,
    max_records: int = 1000,
    has_coordinate: bool = True,
    required_taxon_key: int | None = None,
    license_code: str | None = None,
    occurrence_status: str | None = None,
) -> Any:
    """GBIF bird occurrence source with optional public-release constraints.

    GBIF restricts high-offset occurrence searches and recommends bulk downloads
    for large extractions. Keep this public-site source below that boundary and
    reserve a small portion for Rufous Hummingbird so an unspecified general
    search ordering cannot omit the product's namesake species.
    """
    loaded_at = pendulum.now().isoformat()

    @dlt.resource(
        primary_key="key",
        write_disposition="merge",
        columns=_OCCURRENCE_COLUMNS,
    )
    def occurrences() -> Iterator[dict[str, Any]]:
        if max_records <= 0:
            return

        if max_records > GBIF_SEARCH_RECORD_CAP:
            raise ValueError(
                f"GBIF occurrence-search max_records cannot exceed {GBIF_SEARCH_RECORD_CAP:,}"
            )

        base_params = _occurrence_params(
            country_code=country_code,
            state_province=state_province,
            taxon_key=taxon_key,
            dataset_key=dataset_key,
            has_coordinate=has_coordinate,
            license_code=license_code,
            occurrence_status=occurrence_status,
        )

        reserve = 0
        if required_taxon_key is not None and max_records >= 2 * GBIF_RUFOUS_RESERVE:
            reserve = min(GBIF_RUFOUS_RESERVE, max_records // 10)
        query_budgets: list[tuple[dict[str, Any], int, int]] = [
            (base_params, max_records - reserve, taxon_key)
        ]
        if reserve and required_taxon_key is not None:
            query_budgets.append(
                ({**base_params, "taxonKey": required_taxon_key}, reserve, required_taxon_key)
            )

        seen_keys: set[int] = set()
        for query_params, budget, query_taxon_key in query_budgets:
            query_yielded = 0
            offset = 0
            while query_yielded < budget:
                limit = min(GBIF_PAGE_LIMIT, budget - query_yielded)
                params = {**query_params, "limit": limit, "offset": offset}
                response = dlt_requests.get(
                    GBIF_OCCURRENCE_SEARCH,
                    headers={"Accept": "application/json"},
                    params=params,
                    timeout=GBIF_REQUEST_TIMEOUT_SECONDS,
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
                        taxon_key=query_taxon_key,
                        dataset_key=dataset_key,
                        loaded_at=loaded_at,
                    )
                    key = row["key"]
                    if isinstance(key, int) and key not in seen_keys:
                        seen_keys.add(key)
                        yield row
                        query_yielded += 1
                        if query_yielded >= budget:
                            break

                log.info(
                    "occurrences_page_fetched",
                    count=len(results),
                    offset=offset,
                    query_taxon_key=query_taxon_key,
                )
                if payload.get("endOfRecords") or len(results) < limit:
                    break
                offset += len(results)

    return [occurrences]
