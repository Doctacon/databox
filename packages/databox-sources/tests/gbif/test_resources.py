"""Unit tests for GBIF dlt resources."""

from __future__ import annotations

from typing import Any

import pytest
from databox.orchestration.domains import gbif as gbif_domain
from databox_sources.gbif import source as gbif_module
from databox_sources.gbif.source import GBIF_AVES_TAXON_KEY, process_occurrence


def _occurrence_payload() -> dict[str, Any]:
    return {
        "key": 123,
        "gbifID": "123",
        "occurrenceID": "urn:catalog:abc:123",
        "datasetKey": "dataset-1",
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
        loaded_at="2026-07-08T00:00:00Z",
    )

    assert row["key"] == 123
    assert row["gbif_id"] == "123"
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
    assert row["_loaded_at"] == "2026-07-08T00:00:00Z"


@pytest.mark.vcr
def test_occurrences_resource_fetches_public_search_endpoint() -> None:
    source = gbif_domain._build_source(max_records=2)
    rows = list(source.resources["occurrences"])

    assert len(rows) == 2
    assert all(row["key"] is not None for row in rows)
    assert all(row["_source_url"] == gbif_module.GBIF_OCCURRENCE_SEARCH for row in rows)
    assert all(row["_query_country_code"] == "US" for row in rows)
    assert all(row["_query_state_province"] == "Arizona" for row in rows)
    assert all(row["_query_taxon_key"] == GBIF_AVES_TAXON_KEY for row in rows)


def test_canonical_builder_owns_production_defaults(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    sentinel = object()

    def fake_source(**kwargs: Any) -> object:
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(gbif_domain, "gbif_source", fake_source)
    assert gbif_domain._build_source() is sentinel
    assert gbif_domain._build_source(max_records=2) is sentinel
    assert calls == [
        {
            "country_code": "US",
            "state_province": "Arizona",
            "taxon_key": GBIF_AVES_TAXON_KEY,
            "max_records": 1000,
            "has_coordinate": True,
        },
        {
            "country_code": "US",
            "state_province": "Arizona",
            "taxon_key": GBIF_AVES_TAXON_KEY,
            "max_records": 2,
            "has_coordinate": True,
        },
    ]
