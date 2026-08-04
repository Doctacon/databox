"""Strict candidate and request-boundary tests for iNaturalist."""

from __future__ import annotations

import json
from typing import Any

import pytest
from databox_sources._public_inaturalist import source as inat
from dlt.extract.exceptions import ResourceExtractionError

from .conftest import TARGET, FakeResponse


def test_only_strict_commercial_candidates_survive_first_twenty(
    inaturalist_source_factory: Any,
    inaturalist_transport: list[dict[str, Any]],
) -> None:
    source = inaturalist_source_factory()
    candidates = list(source.resources["photo_candidates"])
    species = list(source.resources["photo_species_results"])
    runs = list(source.resources["photo_discovery_runs"])

    assert [item["photo_id"] for item in candidates] == [1, 2, 3]
    assert [item["license_code"] for item in candidates] == [
        "CC0 1.0",
        "CC BY 4.0",
        "CC BY-SA 4.0",
    ]
    assert inat.INATURALIST_SHARED_CC_VERSION == "4.0"
    assert [item["license_url"] for item in candidates] == [
        "https://creativecommons.org/publicdomain/zero/1.0/",
        "https://creativecommons.org/licenses/by/4.0/",
        "https://creativecommons.org/licenses/by-sa/4.0/",
    ]
    assert candidates[0]["source_page_url"] == "https://www.inaturalist.org/photos/1"
    assert candidates[0]["source_image_original_url"] == (
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpg"
    )
    assert candidates[0]["source_image_large_url"] == (
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/large.jpg"
    )
    assert candidates[0]["original_width"] == 1600
    assert candidates[0]["original_height"] == 1200

    assert species[0]["identity_status"] == "exact_active_species"
    assert species[0]["curated_photo_count"] == 21
    assert species[0]["curated_photos_inspected"] == 20
    assert species[0]["eligible_candidate_count"] == 3
    assert json.loads(species[0]["rejection_counts_json"]) == {
        "creator": 1,
        "dimensions": 1,
        "duplicate": 1,
        "license": 11,
        "malformed": 1,
        "url": 2,
    }
    assert runs[0]["status"] == "complete"
    assert runs[0]["request_count"] == 2
    assert runs[0]["curated_photos_inspected"] == 20
    assert runs[0]["eligible_candidate_count"] == 3

    assert len(inaturalist_transport) == 2
    assert all(call["allow_redirects"] is False for call in inaturalist_transport)
    assert all(call["stream"] is True for call in inaturalist_transport)
    assert all("Authorization" not in call["headers"] for call in inaturalist_transport)
    assert inaturalist_transport[0]["params"] == {
        "q": TARGET["scientific_name"],
        "rank": "species",
        "fields": "id,name,rank,is_active",
        "per_page": 20,
    }


def test_identity_must_be_one_exact_active_species(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_get(endpoint: str, **_kwargs: Any) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(
            endpoint,
            {
                "results": [
                    {
                        "id": 10,
                        "name": TARGET["scientific_name"],
                        "rank": "species",
                        "is_active": False,
                    }
                ]
            },
        )

    monkeypatch.setattr(inat, "_http_get", fake_get)
    source = inat.inaturalist_public_photo_source(
        missing_species=[TARGET], run_id="identity-run", loaded_at="2026-08-03T12:00:00Z"
    )
    assert list(source.resources["photo_candidates"]) == []
    species = list(source.resources["photo_species_results"])
    assert species[0]["identity_status"] == "unavailable"
    assert species[0]["taxon_id"] is None
    assert calls == 1


def test_source_requires_explicit_bounded_missing_targets() -> None:
    source = inat.inaturalist_public_photo_source()
    with pytest.raises(ResourceExtractionError, match="missing_species must be supplied"):
        list(source.resources["photo_candidates"])
    with pytest.raises(ValueError, match="binomial"):
        inat.inaturalist_public_photo_source(
            missing_species=[{**TARGET, "scientific_name": "Selasphorus rufus hybrid"}]
        )
    with pytest.raises(ValueError, match="request_max_attempts"):
        inat.inaturalist_public_photo_source(missing_species=[TARGET], request_max_attempts=4)


def test_retry_count_and_response_size_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def unavailable(endpoint: str, **_kwargs: Any) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(endpoint, {}, status_code=503)

    monkeypatch.setattr(inat, "_http_get", unavailable)
    monkeypatch.setattr(inat.time, "sleep", lambda _seconds: None)
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        inat._request_json(inat.INATURALIST_V2_TAXA_URL, {}, max_attempts=3)
    assert calls == 3

    monkeypatch.setattr(
        inat,
        "_http_get",
        lambda endpoint, **_kwargs: FakeResponse(
            endpoint, {}, declared=inat.INATURALIST_MAX_RESPONSE_BYTES + 1
        ),
    )
    with pytest.raises(RuntimeError, match="byte limit"):
        inat._request_json(inat.INATURALIST_V2_TAXA_URL, {}, max_attempts=1)


@pytest.mark.parametrize(
    "value",
    [
        "http://inaturalist-open-data.s3.amazonaws.com/photos/1/medium.jpg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/2/medium.jpg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/medium.svg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/medium.jpg?token=x",
        "https://images.example.invalid/photos/1/medium.jpg",
    ],
)
def test_photo_url_must_be_exact_public_s3_object(value: str) -> None:
    assert inat._strict_photo_urls(value, value, photo_id=1) is None


def test_original_and_large_urls_are_used_exactly_without_inventing_extensions() -> None:
    assert inat._strict_photo_urls(
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpeg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/large.jpg",
        photo_id=1,
    ) == (
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpeg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/large.jpg",
    )
