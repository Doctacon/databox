"""Deterministic request-time recommendation media selection tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from databox.agent_tools import recommendation_media
from databox.agent_tools.recommendation_media import (
    MAX_CANDIDATES,
    XENO_CANTO_RECORDINGS,
    enrich_recommendation_media,
)
from databox.curated_photo import CuratedPhotoResult


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: str
    scientific_name: str | None


@pytest.fixture(autouse=True)
def _deterministic_curated_selector(monkeypatch: Any) -> None:
    def select(scientific_name: str, **_kwargs: Any) -> CuratedPhotoResult:
        return CuratedPhotoResult(
            status="available",
            source="inaturalist",
            source_record_id="42",
            species_name=scientific_name,
            display_url="https://inaturalist-open-data.s3.amazonaws.com/photos/42/large.jpg",
            source_url="https://www.inaturalist.org/photos/42",
            creator="Fixture Creator",
            license_code="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            original_width=1600,
            original_height=1200,
            selection_reason="Deterministic curated fixture",
            lookup_at="2026-07-12T00:00:00+00:00",
            identity={"taxon_id": 7, "photo_id": 42, "curated_position": 1},
            attempted_sources=("inaturalist",),
        )

    monkeypatch.setattr("databox.curated_photo.select_curated_photo", select)


def _xeno_recording(
    species: str,
    recording_id: int,
    *,
    recording_type: str = "call",
    quality: str = "A",
    license_value: str = "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    recordist: str | None = "Grace Recorder",
    source_url: str | None = None,
    audio_url: str | None = None,
    country: str = "United States",
    locality: str = "Arizona",
) -> dict[str, Any]:
    genus, epithet = species.split()
    return {
        "id": str(recording_id),
        "gen": genus,
        "sp": epithet,
        "rec": recordist,
        "cnt": country,
        "loc": locality,
        "type": recording_type,
        "q": quality,
        "url": source_url or f"//xeno-canto.org/{recording_id}",
        "file": audio_url or f"https://xeno-canto.org/{recording_id}/download",
        "lic": license_value,
    }


def test_queen_valley_fixture_persists_one_photo_and_call_for_all_eight_species() -> None:
    species = [
        "Anser rossii",
        "Pelecanus erythrorhynchos",
        "Aythya collaris",
        "Psaltriparus minimus",
        "Xanthocephalus xanthocephalus",
        "Mimus polyglottos",
        "Fulica americana",
        "Anas platyrhynchos",
    ]
    recommendations = [Recommendation(f"rec-{index}", name) for index, name in enumerate(species)]
    calls: list[tuple[str, Mapping[str, object]]] = []

    def xeno(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        assert endpoint == XENO_CANTO_RECORDINGS
        assert params["per_page"] == MAX_CANDIDATES
        calls.append((endpoint, params))
        query = str(params["query"])
        name = next(
            name for name in species if name.split()[0] in query and name.split()[1] in query
        )
        global_only = name in {"Anser rossii", "Pelecanus erythrorhynchos"}
        if global_only and 'loc:"Arizona"' in query:
            return {"recordings": []}
        index = species.index(name) + 1
        return {
            "recordings": [
                _xeno_recording(
                    name,
                    2000 + index,
                    country="Canada" if global_only else "United States",
                    locality="Ontario" if global_only else "Arizona",
                )
            ]
        }

    result = enrich_recommendation_media(
        recommendations,
        xeno_getter=xeno,
        xeno_api_key="test-key",
    )

    assert len(result.evidence) == 16
    assert result.available_photos == 8
    assert result.available_calls == 8
    assert result.arizona_calls == 6
    assert result.global_calls == 2
    assert result.lookup_count == 18
    for recommendation in recommendations:
        linked = [
            row
            for row in result.evidence
            if row.recommendation_id == recommendation.recommendation_id
        ]
        assert [row.evidence_type for row in linked] == [
            "recommendation_photo",
            "recommendation_call",
        ]
        assert all(row.status == "available" for row in linked)
    global_species = {
        row.summary["species_name"]
        for row in result.evidence
        if row.summary.get("geographic_scope") == "Global example"
    }
    assert global_species == {"Anser rossii", "Pelecanus erythrorhynchos"}
    assert all("test-key" not in str(row) for row in result.evidence)


def test_production_photo_enrichment_uses_curated_selector_metadata(
    monkeypatch: Any,
) -> None:
    selected: list[str] = []

    def select(scientific_name: str, **kwargs: Any) -> CuratedPhotoResult:
        selected.append(scientific_name)
        assert kwargs["getter"] is None
        return CuratedPhotoResult(
            status="available",
            source="inaturalist",
            source_record_id="42",
            species_name=scientific_name,
            display_url="https://inaturalist-open-data.s3.amazonaws.com/photos/42/large.jpg",
            source_url="https://www.inaturalist.org/photos/42",
            creator="Fixture Creator",
            license_code="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            original_width=1600,
            original_height=1200,
            selection_reason="Curated fixture",
            lookup_at="2026-07-12T00:00:00+00:00",
            identity={"taxon_id": 7},
            attempted_sources=("inaturalist",),
        )

    monkeypatch.setattr("databox.curated_photo.select_curated_photo", select)
    batch = enrich_recommendation_media(
        [Recommendation("rec-bluebird", "Sialia mexicana")],
        evidence_types=frozenset({"recommendation_photo"}),
    )
    assert selected == ["Sialia mexicana"]
    assert batch.lookup_count == 1
    assert batch.available_photos == 1
    assert batch.evidence == [
        recommendation_media.RecommendationMediaEvidence(
            recommendation_id="rec-bluebird",
            source="inaturalist",
            source_record_id="42",
            evidence_type="recommendation_photo",
            status="available",
            summary={
                "provider": "inaturalist",
                "species_name": "Sialia mexicana",
                "display_url": "https://inaturalist-open-data.s3.amazonaws.com/photos/42/large.jpg",
                "source_url": "https://www.inaturalist.org/photos/42",
                "creator": "Fixture Creator",
                "rights_holder": None,
                "publisher": None,
                "format": None,
                "license_text": "CC BY 4.0",
                "license_code": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "original_width": 1600,
                "original_height": 1200,
                "selection_reason": "Curated fixture",
            },
            payload={
                "identity": {"taxon_id": 7},
                "attempted_sources": ["inaturalist"],
                "request_count": 0,
                "failure_class": None,
                "retryable": False,
            },
            caveats=[],
        )
    ]


def test_call_selection_prefers_arizona_then_call_quality_and_numeric_id() -> None:
    local_rows = [
        _xeno_recording("Melanerpes formicivorus", 100, recording_type="song", quality="A"),
        _xeno_recording("Melanerpes formicivorus", 30, recording_type="call", quality="B"),
        _xeno_recording("Melanerpes formicivorus", 20, recording_type="alarm call", quality="B"),
        _xeno_recording(
            "Melanerpes formicivorus",
            20,
            recording_type="alarm call",
            quality="B",
            recordist="Zed Recorder",
        ),
        _xeno_recording("Melanerpes formicivorus", 10, recording_type="call", quality="C"),
        _xeno_recording(
            "Melanerpes formicivorus",
            1,
            recording_type="call",
            quality="A",
            source_url="https://xeno-canto.org/999",
        ),
        _xeno_recording("Sialia mexicana", 2, recording_type="call", quality="A"),
    ]

    def run(rows: list[dict[str, Any]]) -> object:
        return enrich_recommendation_media(
            [Recommendation("rec-acorn", "Melanerpes formicivorus")],
            xeno_getter=lambda endpoint, params: {"recordings": rows},
            xeno_api_key="test-key",
        ).evidence[1]

    call = run(local_rows)
    reversed_call = run(list(reversed(local_rows)))
    assert call == reversed_call
    assert call.status == "available"
    assert call.source_record_id == "20"
    assert call.summary["geographic_scope"] == "Arizona"
    assert call.summary["audio_url"] == "https://xeno-canto.org/20/download"
    assert call.summary["license_code"] == "CC BY-NC-SA 4.0"


@pytest.mark.parametrize(
    ("field", "left", "right"),
    [
        ("recordist", "Alice", "ALICE"),
        ("recording_type", "Call", "CALL"),
        ("locality", "Arizona", "ARIZONA"),
    ],
)
def test_case_equivalent_xeno_outputs_have_total_order_when_reversed(
    field: str, left: str, right: str
) -> None:
    base: dict[str, Any] = {
        "recordist": "Fixture Recorder",
        "recording_type": "call",
        "locality": "Arizona",
    }
    left_values = {**base, field: left}
    right_values = {**base, field: right}
    rows = [
        _xeno_recording("Melanerpes formicivorus", 55, **left_values),
        _xeno_recording("Melanerpes formicivorus", 55, **right_values),
    ]

    def run(candidates: list[dict[str, Any]]) -> object:
        return enrich_recommendation_media(
            [Recommendation("rec-case", "Melanerpes formicivorus")],
            xeno_getter=lambda endpoint, params: {"recordings": candidates},
            xeno_api_key="test-key",
        ).evidence[1]

    selected = run(rows)
    reversed_selected = run(list(reversed(rows)))
    assert selected == reversed_selected
    assert selected.status == "available"
    assert selected.summary[field] == min(left, right)


def test_call_global_fallback_and_transport_or_malformed_failures_are_typed_unavailable() -> None:
    queries: list[str] = []

    def global_only(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        query = str(params["query"])
        queries.append(query)
        return (
            {"recordings": []}
            if 'loc:"Arizona"' in query
            else {"recordings": [_xeno_recording("Anser rossii", 77)]}
        )

    global_result = enrich_recommendation_media(
        [Recommendation("rec-ross", "Anser rossii")],
        xeno_getter=global_only,
        xeno_api_key="test-key",
    )
    call = global_result.evidence[1]
    assert len(queries) == 2
    assert call.status == "available"
    assert call.summary["geographic_scope"] == "Global example"

    def timeout(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        raise TimeoutError("private transport detail")

    partial = enrich_recommendation_media(
        [Recommendation("rec-partial", "Anser rossii")],
        xeno_getter=global_only,
        xeno_api_key="test-key",
    )
    assert [row.status for row in partial.evidence] == ["available", "available"]

    unavailable = enrich_recommendation_media(
        [
            Recommendation("rec-timeout", "Anser rossii"),
            Recommendation("rec-no-name", None),
        ],
        xeno_getter=lambda endpoint, params: {"unexpected": []},
        xeno_api_key="test-key",
    )
    assert len(unavailable.evidence) == 4
    assert [row.status for row in unavailable.evidence] == [
        "available",
        "unavailable",
        "unavailable",
        "unavailable",
    ]
    assert "private transport detail" not in str(unavailable)
    assert [row.evidence_type for row in unavailable.evidence] == [
        "recommendation_photo",
        "recommendation_call",
        "recommendation_photo",
        "recommendation_call",
    ]


def test_xeno_identity_url_license_attribution_attacks_fail_closed() -> None:
    rows = [
        _xeno_recording("Anser rossii", 1, source_url="https://evil.example/1"),
        _xeno_recording("Anser rossii", 2, audio_url="https://xeno-canto.org/3/download"),
        _xeno_recording("Anser rossii", 3, license_value="all rights reserved"),
        _xeno_recording("Anser rossii", 4, recordist=None),
        _xeno_recording("Branta canadensis", 5),
    ]
    result = enrich_recommendation_media(
        [Recommendation("rec-ross", "Anser rossii")],
        xeno_getter=lambda endpoint, params: {"recordings": rows},
        xeno_api_key="test-key",
    )
    assert result.evidence[1].status == "unavailable"
    assert result.lookup_count == 3


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("CC0_1_0", "CC0 1.0"),
        ("CC_BY_4_0", "CC BY 4.0"),
        ("https://creativecommons.org/licenses/by-sa/3.0/", "CC BY-SA 3.0"),
        ("CC BY-NC 2.5", "CC BY-NC 2.5"),
        ("https://creativecommons.org/licenses/by-nc-sa/4.0/", "CC BY-NC-SA 4.0"),
    ],
)
def test_ratified_photo_license_allowlist(value: str, expected: str) -> None:
    parsed = recommendation_media.parse_creative_commons_license(value, allow_audio_nd=False)
    assert parsed is not None
    assert parsed[0] == expected
    assert parsed[2] is False


@pytest.mark.parametrize(
    "value",
    [
        "https://creativecommons.org/licenses/sampling/1.0/",
        "https://creativecommons.org/licenses/by/999.999/",
        "https://creativecommons.org/licenses/by/4..0/",
        "CC0 4.0",
        "CC BY-ND 4.0",
        "CC BY-NC-ND 4.0",
    ],
)
def test_unknown_insane_and_photo_nd_licenses_fail_closed(value: str) -> None:
    assert recommendation_media.parse_creative_commons_license(value, allow_audio_nd=False) is None


def test_selective_photo_enrichment_does_not_invoke_xeno() -> None:
    recommendation = Recommendation("rec-photo", "Sialia mexicana")

    result = enrich_recommendation_media(
        [recommendation],
        xeno_getter=lambda *_: (_ for _ in ()).throw(AssertionError("unexpected Xeno lookup")),
        xeno_api_key="test-key",
        evidence_types=frozenset({"recommendation_photo"}),
    )
    assert [row.evidence_type for row in result.evidence] == ["recommendation_photo"]
    assert result.lookup_count == 1


def test_http_creative_commons_license_is_canonicalized_to_https() -> None:
    parsed = recommendation_media.parse_creative_commons_license(
        "http://creativecommons.org/licenses/by-nc/4.0/", allow_audio_nd=False
    )
    assert parsed == (
        "CC BY-NC 4.0",
        "https://creativecommons.org/licenses/by-nc/4.0/",
        False,
    )
    assert (
        recommendation_media.parse_creative_commons_license(
            "http://evil.example/licenses/by-nc/4.0/", allow_audio_nd=False
        )
        is None
    )


def test_unchanged_audio_nd_variants_are_explicitly_allowed() -> None:
    for value in (
        "https://creativecommons.org/licenses/by-nd/4.0/",
        "CC_BY_NC_ND_3_0",
    ):
        parsed = recommendation_media.parse_creative_commons_license(value, allow_audio_nd=True)
        assert parsed is not None
        assert parsed[2] is True


def test_default_transport_response_bytes_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OversizedResponse:
        headers = {"Content-Length": str(recommendation_media.MAX_RESPONSE_BYTES + 1)}

        def __enter__(self) -> OversizedResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            raise AssertionError(f"oversized response must fail before read: {size}")

    observed_timeout: list[float] = []

    def fake_urlopen(request: object, *, timeout: float) -> OversizedResponse:
        observed_timeout.append(timeout)
        return OversizedResponse()

    monkeypatch.setattr(recommendation_media, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="discovery failed"):
        recommendation_media._get_json(XENO_CANTO_RECORDINGS, {"query": "x"})
    assert observed_timeout == [recommendation_media.HTTP_TIMEOUT_SECONDS]


@pytest.mark.parametrize(
    "failure",
    [
        HTTPError(
            "https://xeno-canto.org/api/3/recordings?key=secret-key",
            503,
            "private HTTP detail",
            {},
            None,
        ),
        URLError("private URL detail key=secret-key"),
        TimeoutError("private timeout detail key=secret-key"),
    ],
)
def test_default_transport_suppresses_url_key_and_exception_causes(
    monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    def fail(request: object, *, timeout: float) -> object:
        _ = request, timeout
        raise failure

    monkeypatch.setattr(recommendation_media, "urlopen", fail)
    with pytest.raises(RuntimeError, match="^recommendation-media discovery failed$") as exc_info:
        recommendation_media._get_json(
            XENO_CANTO_RECORDINGS, {"query": 'gen:"Anser" sp:"rossii"', "key": "secret-key"}
        )
    error = exc_info.value
    assert error.__cause__ is None
    assert error.__context__ is None
    rendered = f"{error!s} {error!r} {error.__dict__!r}"
    assert "secret-key" not in rendered
    assert "xeno-canto.org" not in rendered
    assert "private" not in rendered


def test_missing_xeno_key_and_candidate_bounds_are_explicit() -> None:
    calls = 0

    def must_not_call(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"recordings": []}

    result = enrich_recommendation_media(
        [Recommendation("rec", "Sialia mexicana")],
        xeno_getter=must_not_call,
        xeno_api_key="",
    )
    assert calls == 0
    assert result.lookup_count == 1
    assert result.evidence[1].status == "unavailable"
    assert result.evidence[1].caveats == ["Xeno-canto call lookup is not configured"]
