"""Deterministic curated iNaturalist representative-photo tests."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest
from databox import curated_photo as module
from databox.curated_photo import (
    INATURALIST_V1_TAXON,
    INATURALIST_V2_TAXA,
    CuratedPhotoResult,
    InaturalistRateLimiter,
    curated_photo_outcome_keys,
    curated_photo_result_is_safe,
    safe_inaturalist_display_url,
    safe_inaturalist_source_url,
    select_curated_photo,
)

SPECIES = "Trogon elegans"
NOW = datetime(2026, 7, 13, tzinfo=UTC)


def v2(*rows: dict[str, object]) -> dict[str, object]:
    return {"results": list(rows)}


def taxon(
    taxon_id: int = 10, *, name: str = SPECIES, photos: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "results": [
            {
                "id": taxon_id,
                "name": name,
                "rank": "species",
                "is_active": True,
                "taxon_photos": photos or [],
            }
        ]
    }


def photo(
    photo_id: int,
    *,
    license_code: str | None = "cc-by",
    width: int = 1600,
    height: int = 1200,
    attribution: str = "Ada Birder",
    host: str = "inaturalist-open-data.s3.amazonaws.com",
) -> dict[str, object]:
    return {
        "photo": {
            "id": photo_id,
            "license_code": license_code,
            "attribution": attribution,
            "url": f"https://{host}/photos/{photo_id}/medium.jpg",
            "original_dimensions": {"width": width, "height": height},
        }
    }


class Getter:
    def __init__(self, v2_payload: dict[str, object], v1_payload: dict[str, object]) -> None:
        self.v2_payload = v2_payload
        self.v1_payload = v1_payload
        self.calls: list[str] = []

    def __call__(self, endpoint: str, _params: object) -> dict[str, Any]:
        self.calls.append(endpoint)
        if endpoint == INATURALIST_V2_TAXA:
            return self.v2_payload  # type: ignore[return-value]
        if endpoint == INATURALIST_V1_TAXON.format(taxon_id=10):
            return self.v1_payload  # type: ignore[return-value]
        raise AssertionError(f"unexpected endpoint {endpoint}")


def select(getter: Getter, name: object = SPECIES) -> CuratedPhotoResult:
    return select_curated_photo(
        name, getter=getter, before_inaturalist_request=lambda: None, now=lambda: NOW
    )


def test_first_eligible_curated_photo_wins_without_other_provider_requests() -> None:
    getter = Getter(
        v2({"id": 10, "name": SPECIES, "rank": "species", "is_active": True}),
        taxon(
            photos=[
                photo(1, license_code=None),
                photo(2, width=900, height=900),
                photo(3),
                photo(4),
            ]
        ),
    )
    result = select(getter)
    assert result.status == "available"
    assert result.source == "inaturalist"
    assert result.source_record_id == "3"
    assert result.identity == {"taxon_id": 10, "photo_id": 3, "curated_position": 3}
    assert result.attempted_sources == ("inaturalist",)
    assert result.request_count == 2
    assert result.retryable is False
    assert getter.calls == [INATURALIST_V2_TAXA, INATURALIST_V1_TAXON.format(taxon_id=10)]
    assert curated_photo_result_is_safe(result, SPECIES)


@pytest.mark.parametrize(
    "width,height,available",
    [(900, 900, False), (1200, 700, False), (1000, 750, True), (750, 1000, True)],
)
def test_dimension_floor(width: int, height: int, available: bool) -> None:
    result = select(
        Getter(
            v2({"id": 10, "name": SPECIES, "rank": "species", "is_active": True}),
            taxon(photos=[photo(1, width=width, height=height)]),
        )
    )
    assert (result.status == "available") is available


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"id": 10, "name": SPECIES, "rank": "subspecies", "is_active": True}],
        [{"id": 10, "name": SPECIES, "rank": "species", "is_active": False}],
        [
            {"id": 10, "name": SPECIES, "rank": "species", "is_active": True},
            {"id": 11, "name": SPECIES, "rank": "species", "is_active": True},
        ],
    ],
)
def test_exact_active_species_identity_is_required(rows: list[dict[str, object]]) -> None:
    result = select(Getter(v2(*rows), taxon(photos=[photo(1)])))
    assert result.status == "unavailable"
    assert result.attempted_sources == ("inaturalist",)


def test_cross_version_identity_mismatch_fails_closed() -> None:
    result = select(
        Getter(
            v2({"id": 10, "name": SPECIES, "rank": "species", "is_active": True}),
            taxon(name="Other bird", photos=[photo(1)]),
        )
    )
    assert result.status == "unavailable"


def test_non_binomial_makes_no_request() -> None:
    getter = Getter(v2(), taxon())
    result = select(getter, "Trogon elegans x ambiguus")
    assert result.status == "unavailable"
    assert result.species_name is None
    assert result.attempted_sources == ()
    assert result.request_count == 0
    assert getter.calls == []
    assert curated_photo_result_is_safe(result, "Trogon elegans x ambiguus")


@pytest.mark.parametrize(
    "candidate",
    [
        photo(1, license_code="cc-by-nd"),
        photo(1, attribution="<script></script>"),
        photo(1, host="evil.example"),
        photo(1, license_code=None),
    ],
)
def test_unsafe_or_ineligible_candidate_yields_typed_unavailable(
    candidate: dict[str, object],
) -> None:
    result = select(
        Getter(
            v2({"id": 10, "name": SPECIES, "rank": "species", "is_active": True}),
            taxon(photos=[candidate]),
        )
    )
    assert result.status == "unavailable"
    assert result.source == "curated_photo"
    assert result.attempted_sources == ("inaturalist",)
    assert curated_photo_result_is_safe(result, SPECIES)


def test_persisted_contract_rejects_legacy_provider_and_attempt_order() -> None:
    good = select(
        Getter(
            v2({"id": 10, "name": SPECIES, "rank": "species", "is_active": True}),
            taxon(photos=[photo(1)]),
        )
    )
    legacy_provider = CuratedPhotoResult(**{**good.__dict__, "source": "wikimedia_commons"})  # type: ignore[arg-type]
    legacy_attempts = CuratedPhotoResult(
        **{**good.__dict__, "attempted_sources": ("wikimedia_commons", "inaturalist")}
    )
    assert not curated_photo_result_is_safe(legacy_provider, SPECIES)
    assert not curated_photo_result_is_safe(legacy_attempts, SPECIES)


@pytest.mark.parametrize(
    "url",
    [
        "http://inaturalist-open-data.s3.amazonaws.com/photos/1/large.jpg",
        "https://evil.example/photos/1/large.jpg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/2/large.jpg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/large.svg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/1/large.jpg?x=1",
    ],
)
def test_display_url_validator_rejects_adversarial_urls(url: str) -> None:
    assert safe_inaturalist_display_url(url, photo_id=1) is None


def test_source_url_validator_is_exact() -> None:
    assert safe_inaturalist_source_url("https://www.inaturalist.org/photos/1", photo_id=1)
    assert not safe_inaturalist_source_url("https://www.inaturalist.org:443/photos/1", photo_id=1)
    assert not safe_inaturalist_source_url("https://www.inaturalist.org/photos/2", photo_id=1)


def test_outcome_keys_are_bounded() -> None:
    available = select(
        Getter(
            v2({"id": 10, "name": SPECIES, "rank": "species", "is_active": True}),
            taxon(photos=[photo(1)]),
        )
    )
    unavailable = select(
        Getter(v2({"id": 10, "name": SPECIES, "rank": "species", "is_active": True}), taxon())
    )
    failure = select(Getter({}, {}))
    assert failure.request_count == 1
    assert failure.retryable is True
    assert failure.failure_class == "schema"
    assert curated_photo_outcome_keys(available) == ("inaturalist.available",)
    assert curated_photo_outcome_keys(unavailable) == ("inaturalist.no_eligible",)
    assert curated_photo_outcome_keys(failure) == ("inaturalist.failed.schema",)


def test_default_transport_rejects_redirect_and_oversized_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        headers = {"Content-Length": str(module.MAX_RESPONSE_BYTES + 1)}

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return "https://evil.example/private"

        def read(self, _size: int) -> bytes:
            return json.dumps({}).encode()

    monkeypatch.setattr(module, "_open_metadata_request", lambda _request: Response())
    with pytest.raises(RuntimeError, match="metadata discovery failed"):
        module._get_json(INATURALIST_V2_TAXA, {})


def test_default_transport_does_not_retry_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fail(_request: object) -> object:
        nonlocal calls
        calls += 1
        raise HTTPError(INATURALIST_V2_TAXA, 503, "down", {}, None)

    monkeypatch.setattr(module, "_open_metadata_request", fail)
    with pytest.raises(RuntimeError):
        module._get_json(INATURALIST_V2_TAXA, {})
    assert calls == 1


def test_rate_limiter_enforces_daily_budget_without_shared_state(tmp_path: Path) -> None:
    state = tmp_path / "rate.json"
    limiter = InaturalistRateLimiter(state_path=state, interval_seconds=0, daily_limit=1)
    limiter.wait()
    with pytest.raises(RuntimeError, match="daily metadata request budget"):
        InaturalistRateLimiter(state_path=state, interval_seconds=0, daily_limit=1).wait()
    assert json.loads(state.read_text())["count"] == 1


def test_rate_limiter_coordinates_instances_and_restart(tmp_path: Path) -> None:
    state = tmp_path / "rate.json"
    first = InaturalistRateLimiter(state_path=state, interval_seconds=0, daily_limit=3)
    second = InaturalistRateLimiter(state_path=state, interval_seconds=0, daily_limit=3)
    first.wait()
    second.wait()
    InaturalistRateLimiter(state_path=state, interval_seconds=0, daily_limit=3).wait()
    with pytest.raises(RuntimeError, match="daily metadata request budget"):
        first.wait()
    assert json.loads(state.read_text())["count"] == 3


def test_rate_limiter_serializes_separate_processes_in_temporary_state(
    tmp_path: Path,
) -> None:
    state = tmp_path / "cross-process-rate.json"
    code = (
        "from databox.curated_photo import InaturalistRateLimiter;"
        f"InaturalistRateLimiter(state_path={str(state)!r}, interval_seconds=0, "
        "daily_limit=2).wait()"
    )
    processes = [subprocess.Popen([sys.executable, "-c", code]) for _ in range(2)]
    assert [process.wait(timeout=30) for process in processes] == [0, 0]
    assert json.loads(state.read_text())["count"] == 2
    with pytest.raises(RuntimeError, match="daily metadata request budget"):
        InaturalistRateLimiter(state_path=state, interval_seconds=0, daily_limit=2).wait()
