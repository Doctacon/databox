"""Offline iNaturalist API fixtures."""

from __future__ import annotations

import json
from typing import Any

import pytest
from databox_sources._public_inaturalist import source as inat

TARGET = {
    "species_code": "gbif-2476855",
    "common_name": "Rufous Hummingbird",
    "scientific_name": "Selasphorus rufus",
}


def photo(
    photo_id: int,
    *,
    license_code: str | None = "cc-by",
    attribution: str = "Ada Birder",
    width: int = 1600,
    height: int = 1200,
    url_photo_id: int | None = None,
    host: str = "inaturalist-open-data.s3.amazonaws.com",
    original_extension: str = "jpg",
) -> dict[str, object]:
    resolved_id = url_photo_id or photo_id
    return {
        "photo": {
            "id": photo_id,
            "license_code": license_code,
            "attribution": attribution,
            "url": f"https://{host}/photos/{resolved_id}/medium.jpg",
            "original_url": (f"https://{host}/photos/{resolved_id}/original.{original_extension}"),
            "large_url": f"https://{host}/photos/{resolved_id}/large.jpg",
            "original_dimensions": {"width": width, "height": height},
        }
    }


def curated_photos() -> list[dict[str, object]]:
    return [
        photo(1, license_code="cc0"),
        photo(2, license_code="cc-by"),
        photo(3, license_code="cc-by-sa"),
        photo(4, license_code="cc-by-nc"),
        photo(5, license_code="cc-by-nd"),
        photo(6, license_code=None),
        photo(7, attribution="Unknown"),
        photo(8, width=900, height=900),
        photo(9, host="images.example.invalid"),
        photo(10, url_photo_id=999),
        {},
        photo(1),
        *[photo(photo_id, license_code="cc-by-nc-sa") for photo_id in range(13, 21)],
        photo(21),
    ]


class FakeResponse:
    def __init__(
        self, endpoint: str, payload: object, *, status_code: int = 200, declared: int | None = None
    ) -> None:
        self.status_code = status_code
        self.url = endpoint
        self.body = json.dumps(payload, separators=(",", ":")).encode()
        self.headers = {"Content-Length": str(declared if declared is not None else len(self.body))}

    def iter_content(self, *, chunk_size: int) -> Any:
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start : start + chunk_size]


@pytest.fixture
def inaturalist_transport(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_get(endpoint: str, **kwargs: Any) -> FakeResponse:
        calls.append({"endpoint": endpoint, **kwargs})
        if endpoint == inat.INATURALIST_V2_TAXA_URL:
            return FakeResponse(
                endpoint,
                {
                    "results": [
                        {
                            "id": 10,
                            "name": TARGET["scientific_name"],
                            "rank": "species",
                            "is_active": True,
                        }
                    ]
                },
            )
        assert endpoint == inat.INATURALIST_V1_TAXON_URL.format(taxon_id=10)
        return FakeResponse(
            endpoint,
            {
                "results": [
                    {
                        "id": 10,
                        "name": TARGET["scientific_name"],
                        "rank": "species",
                        "is_active": True,
                        "taxon_photos": curated_photos(),
                    }
                ]
            },
        )

    monkeypatch.setattr(inat, "_http_get", fake_get)
    return calls


@pytest.fixture
def inaturalist_source_factory(inaturalist_transport: list[dict[str, Any]]) -> Any:
    def factory() -> Any:
        return inat.inaturalist_public_photo_source(
            missing_species=[TARGET],
            run_id="fixture-run",
            loaded_at="2026-08-03T12:00:00Z",
        )

    return factory
