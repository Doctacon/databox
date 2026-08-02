"""Unit tests for GBIF dlt resources."""

from __future__ import annotations

from typing import Any

import pytest
from databox.orchestration.domains import gbif as gbif_domain
from databox_sources.gbif import source as gbif_module
from databox_sources.gbif.source import (
    GBIF_AVES_TAXON_KEY,
    GBIF_EBIRD_EOD_DATASET_CITATION,
    GBIF_EBIRD_EOD_DATASET_DOI,
    GBIF_EBIRD_EOD_DATASET_KEY,
    GBIF_EBIRD_EOD_DATASET_LICENSE,
    GBIF_EBIRD_EOD_DATASET_PUBLISHER,
    GBIF_EBIRD_EOD_DATASET_TITLE,
    GBIF_EBIRD_EOD_DATASET_URL,
    GBIF_RUFOUS_TAXON_KEY,
    process_occurrence,
)


def _occurrence_payload() -> dict[str, Any]:
    return {
        "key": 123,
        "gbifID": "123",
        "occurrenceID": "urn:catalog:abc:123",
        "datasetKey": GBIF_EBIRD_EOD_DATASET_KEY,
        "publishingOrgKey": "org-1",
        "scientificName": "Cyanocitta stelleri (Gmelin, 1788)",
        "acceptedScientificName": "Cyanocitta stelleri (Gmelin, 1788)",
        "vernacularName": "Steller's Jay",
        "class": "Aves",
        "order": "Passeriformes",
        "family": "Corvidae",
        "genus": "Cyanocitta",
        "species": "Cyanocitta stelleri",
        "taxonKey": 2482467,
        "acceptedTaxonKey": 2482467,
        "classKey": GBIF_AVES_TAXON_KEY,
        "decimalLatitude": 34.54,
        "decimalLongitude": -112.47,
        "coordinateUncertaintyInMeters": 25.0,
        "country": "United States",
        "countryCode": "US",
        "stateProvince": "Arizona",
        "locality": "Thumb Butte",
        "eventDate": "2026-07-01T07:30:00",
        "year": 2026,
        "month": 7,
        "day": 1,
        "basisOfRecord": "HUMAN_OBSERVATION",
        "occurrenceStatus": "PRESENT",
        "recordedBy": ["Example Observer"],
        "identifiedBy": "Example Identifier",
        "institutionCode": "iNaturalist",
        "collectionCode": "Observations",
        "catalogNumber": "abc123",
        "license": "http://creativecommons.org/licenses/by-nc/4.0/legalcode",
        "references": "https://www.gbif.org/occurrence/123",
        "lastInterpreted": "2026-07-02T00:00:00Z",
    }


def test_process_occurrence_preserves_planner_fields() -> None:
    row = process_occurrence(
        _occurrence_payload(),
        country_code="US",
        state_province="Arizona",
        taxon_key=GBIF_AVES_TAXON_KEY,
        dataset_key=GBIF_EBIRD_EOD_DATASET_KEY,
        loaded_at="2026-07-08T00:00:00Z",
    )

    assert row["key"] == 123
    assert row["gbif_id"] == "123"
    assert row["dataset_key"] == GBIF_EBIRD_EOD_DATASET_KEY
    assert row["dataset_title"] == GBIF_EBIRD_EOD_DATASET_TITLE
    assert row["dataset_publisher"] == GBIF_EBIRD_EOD_DATASET_PUBLISHER
    assert row["dataset_doi"] == GBIF_EBIRD_EOD_DATASET_DOI
    assert row["dataset_source_url"] == GBIF_EBIRD_EOD_DATASET_URL
    assert row["dataset_license"] == GBIF_EBIRD_EOD_DATASET_LICENSE
    assert row["dataset_citation"].startswith(GBIF_EBIRD_EOD_DATASET_CITATION)
    assert "accessed via GBIF.org on 2026-07-08" in row["dataset_citation"]
    assert row["scientific_name"] == "Cyanocitta stelleri (Gmelin, 1788)"
    assert row["accepted_taxon_key"] == 2482467
    assert row["class_key"] == GBIF_AVES_TAXON_KEY
    assert row["decimal_latitude"] == 34.54
    assert row["decimal_longitude"] == -112.47
    assert row["state_province"] == "Arizona"
    assert row["basis_of_record"] == "HUMAN_OBSERVATION"
    assert row["occurrence_status"] == "PRESENT"
    assert row["recorded_by"] == "Example Observer"
    assert row["license"] == "http://creativecommons.org/licenses/by-nc/4.0/legalcode"
    assert row["references"] == "https://www.gbif.org/occurrence/123"
    assert row["_source_url"] == gbif_module.GBIF_OCCURRENCE_SEARCH
    assert row["_query_country_code"] == "US"
    assert row["_query_state_province"] == "Arizona"
    assert row["_query_taxon_key"] == GBIF_AVES_TAXON_KEY
    assert row["_query_dataset_key"] == GBIF_EBIRD_EOD_DATASET_KEY
    assert row["_loaded_at"] == "2026-07-08T00:00:00Z"


@pytest.mark.vcr
def test_occurrences_resource_fetches_public_search_endpoint() -> None:
    source = gbif_domain._build_source(max_records=2, public_release=True)
    rows = list(source.resources["occurrences"])

    assert len(rows) == 2
    assert all(row["key"] is not None for row in rows)
    assert all(row["_source_url"] == gbif_module.GBIF_OCCURRENCE_SEARCH for row in rows)
    assert all(row["_query_country_code"] == "US" for row in rows)
    assert all(row["_query_state_province"] == "Arizona" for row in rows)
    assert all(row["_query_taxon_key"] == GBIF_AVES_TAXON_KEY for row in rows)
    assert all(row["_query_dataset_key"] == GBIF_EBIRD_EOD_DATASET_KEY for row in rows)
    assert all(row["dataset_key"] == GBIF_EBIRD_EOD_DATASET_KEY for row in rows)
    assert all(row["dataset_publisher"] == GBIF_EBIRD_EOD_DATASET_PUBLISHER for row in rows)


def test_public_sample_reserves_namesake_records_and_stays_bounded(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        def __init__(self, params: dict[str, Any]) -> None:
            self.params = params

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            limit = int(self.params["limit"])
            offset = int(self.params["offset"])
            is_rufous = self.params.get("taxonKey") == GBIF_RUFOUS_TAXON_KEY
            key_base = 1_000_000 if is_rufous else 1
            scientific_name = "Selasphorus rufus" if is_rufous else "Cyanocitta stelleri"
            common_name = "Rufous Hummingbird" if is_rufous else "Steller's Jay"
            return {
                "endOfRecords": False,
                "results": [
                    {
                        "key": key_base + offset + index,
                        "datasetKey": GBIF_EBIRD_EOD_DATASET_KEY,
                        "scientificName": scientific_name,
                        "acceptedScientificName": scientific_name,
                        "vernacularName": common_name,
                        "license": "http://creativecommons.org/licenses/by/4.0/legalcode",
                        "occurrenceStatus": "PRESENT",
                    }
                    for index in range(limit)
                ],
            }

    def fake_get(*args: Any, **kwargs: Any) -> FakeResponse:
        assert args[0] == gbif_module.GBIF_OCCURRENCE_SEARCH
        assert kwargs["timeout"] == gbif_module.GBIF_REQUEST_TIMEOUT_SECONDS
        params = dict(kwargs["params"])
        calls.append(params)
        return FakeResponse(params)

    monkeypatch.setattr(gbif_module.dlt_requests, "get", fake_get)
    source = gbif_module.gbif_source(
        max_records=600,
        dataset_key=GBIF_EBIRD_EOD_DATASET_KEY,
        required_taxon_key=GBIF_RUFOUS_TAXON_KEY,
        license_code="CC_BY_4_0",
        occurrence_status="PRESENT",
    )
    rows = list(source.resources["occurrences"])

    assert len(rows) == 600
    assert sum(row["_query_taxon_key"] == GBIF_RUFOUS_TAXON_KEY for row in rows) == 60
    assert all(call["license"] == "CC_BY_4_0" for call in calls)
    assert all(call["occurrenceStatus"] == "PRESENT" for call in calls)
    assert max(int(call["offset"]) for call in calls) < 10_000


def test_canonical_builder_separates_local_and_public_defaults(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    sentinel = object()

    def fake_source(**kwargs: Any) -> object:
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(gbif_domain, "gbif_source", fake_source)
    assert gbif_domain._build_source() is sentinel
    assert gbif_domain._build_source(max_records=2, public_release=True) is sentinel
    assert calls == [
        {
            "country_code": "US",
            "state_province": "Arizona",
            "taxon_key": GBIF_AVES_TAXON_KEY,
            "dataset_key": None,
            "max_records": 1000,
            "has_coordinate": True,
            "required_taxon_key": None,
            "license_code": None,
            "occurrence_status": None,
        },
        {
            "country_code": "US",
            "state_province": "Arizona",
            "taxon_key": GBIF_AVES_TAXON_KEY,
            "dataset_key": GBIF_EBIRD_EOD_DATASET_KEY,
            "max_records": 2,
            "has_coordinate": True,
            "required_taxon_key": GBIF_RUFOUS_TAXON_KEY,
            "license_code": "CC_BY_4_0",
            "occurrence_status": "PRESENT",
        },
    ]
