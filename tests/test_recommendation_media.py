"""Deterministic request-time recommendation media selection tests."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from databox.agent_tools import recommendation_media
from databox.agent_tools.recommendation_media import (
    GBIF_OCCURRENCE_SEARCH,
    MAX_CANDIDATES,
    XENO_CANTO_RECORDINGS,
    enrich_recommendation_media,
)


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: str
    scientific_name: str | None


def _gbif_media(
    *,
    identifier: str,
    license_value: str = "https://creativecommons.org/licenses/by/4.0/",
    creator: str | None = "Ada Birder",
    media_type: str = "StillImage",
    image_format: str = "image/jpeg",
) -> dict[str, Any]:
    return {
        "type": media_type,
        "format": image_format,
        "identifier": identifier,
        "license": license_value,
        "creator": creator,
        "rightsHolder": None,
    }


def _gbif_occurrence(
    species: str,
    key: int,
    media: list[dict[str, Any]],
    *,
    accepted: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "species": species,
        "acceptedScientificName": accepted or species,
        "countryCode": "US",
        "country": "United States",
        "stateProvince": "Arizona",
        "publishingOrgKey": "Arizona bird archive",
        "media": media,
    }


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


def _gbif_cache_url(key: int, identifier: str) -> str:
    identifier_md5 = hashlib.md5(identifier.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"https://api.gbif.org/v1/image/cache/500x500/occurrence/{key}/media/{identifier_md5}"


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

    def gbif(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        assert endpoint == GBIF_OCCURRENCE_SEARCH
        assert params["country"] == "US"
        assert params["stateProvince"] == "Arizona"
        assert params["mediaType"] == "StillImage"
        assert params["limit"] == MAX_CANDIDATES
        name = str(params["scientificName"])
        index = species.index(name) + 1
        return {
            "results": [
                _gbif_occurrence(
                    name,
                    1000 + index,
                    [_gbif_media(identifier=f"https://images.inaturalist.org/{index}.jpg")],
                )
            ]
        }

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
        gbif_getter=gbif,
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


def test_photo_selection_is_order_independent_and_rejects_identity_license_and_url_attacks() -> (
    None
):
    valid_nd = _gbif_occurrence(
        "Sialia mexicana",
        30,
        [
            _gbif_media(
                identifier="https://images.inaturalist.org/nd.jpg",
                license_value="https://creativecommons.org/licenses/by-nd/4.0/",
            )
        ],
    )
    valid_preferred = _gbif_occurrence(
        "Sialia mexicana",
        20,
        [_gbif_media(identifier="https://images.inaturalist.org/preferred.jpg")],
    )
    lower_stable_id = _gbif_occurrence(
        "Sialia mexicana",
        10,
        [
            _gbif_media(identifier="https://images.inaturalist.org/stable.jpg"),
            _gbif_media(
                identifier="https://images.inaturalist.org/stable.jpg",
                creator="Zed Photographer",
            ),
        ],
    )
    attacks = [
        _gbif_occurrence(
            "Sialia currucoides",
            1,
            [_gbif_media(identifier="https://images.inaturalist.org/wrong-species.jpg")],
        ),
        _gbif_occurrence(
            "Sialia mexicana",
            2,
            [_gbif_media(identifier="http://evil.example/photo.jpg")],
        ),
        _gbif_occurrence(
            "Sialia mexicana",
            3,
            [
                _gbif_media(
                    identifier="https://images.inaturalist.org/unlicensed.jpg",
                    license_value="all rights reserved",
                )
            ],
        ),
        _gbif_occurrence(
            "Sialia mexicana",
            4,
            [_gbif_media(identifier="https://user@images.inaturalist.org/credential.jpg")],
        ),
        _gbif_occurrence(
            "Sialia mexicana",
            5,
            [_gbif_media(identifier="https://images.inaturalist.org/no-credit.jpg", creator=None)],
        ),
        _gbif_occurrence(
            "Sialia mexicana",
            6,
            [
                _gbif_media(
                    identifier="https://images.inaturalist.org/movie.mp4",
                    image_format="video/mp4",
                )
            ],
        ),
    ]
    ordered = [valid_nd, valid_preferred, lower_stable_id, *attacks]

    def run(rows: list[dict[str, Any]]) -> object:
        return enrich_recommendation_media(
            [Recommendation("rec-bluebird", "Sialia mexicana")],
            gbif_getter=lambda endpoint, params: {"results": rows},
            xeno_getter=lambda endpoint, params: {"recordings": []},
            xeno_api_key="test-key",
        ).evidence[0]

    reversed_rows = []
    for row in reversed(ordered):
        reversed_rows.append({**row, "media": list(reversed(row["media"]))})
    first = run(ordered)
    reverse = run(reversed_rows)
    assert first == reverse
    assert first.status == "available"
    assert first.source_record_id == "10"
    assert first.summary["display_url"] == _gbif_cache_url(
        10, "https://images.inaturalist.org/stable.jpg"
    )
    assert first.summary["license_code"] == "CC BY 4.0"
    assert first.payload["original_media_identifier"] == "https://images.inaturalist.org/stable.jpg"
    assert "test-key" not in str(first)


def test_gbif_cache_url_requires_exact_path_key_and_identifier_md5_relation() -> None:
    identifier = "https://images.inaturalist.org/bird.jpg"
    valid = _gbif_cache_url(42, identifier)
    assert (
        recommendation_media.safe_gbif_photo_url(
            valid, occurrence_id="42", original_identifier=identifier
        )
        == valid
    )
    attacks = [
        "https://api.gbif.org/",
        "https://api.gbif.org/v1/occurrence/search",
        valid.replace("/occurrence/42/", "/occurrence/41/"),
        valid[:-1] + ("0" if valid[-1] != "0" else "1"),
        valid.replace("/500x500/", "/9999x9999/"),
        valid + "?download=true",
        valid + "#fragment",
        valid.replace("/occurrence/42/", "/occurrence/42/../42/"),
        valid.replace("api.gbif.org", "user@api.gbif.org"),
    ]
    for attack in attacks:
        assert (
            recommendation_media.safe_gbif_photo_url(
                attack, occurrence_id="42", original_identifier=identifier
            )
            is None
        )


def test_no_derivatives_photo_is_unavailable_without_an_exact_original_policy() -> None:
    def gbif(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        return {
            "results": [
                _gbif_occurrence(
                    "Anser rossii",
                    42,
                    [
                        _gbif_media(
                            identifier="https://evil.example/ross.jpg",
                            license_value="https://creativecommons.org/licenses/by-nc-nd/4.0/",
                        ),
                        _gbif_media(
                            identifier="https://images.inaturalist.org/ross.jpg",
                            license_value="https://creativecommons.org/licenses/by-nc-nd/4.0/",
                        ),
                    ],
                )
            ]
        }

    result = enrich_recommendation_media(
        [Recommendation("rec-ross", "Anser rossii")],
        gbif_getter=gbif,
        xeno_getter=lambda endpoint, params: {"recordings": []},
        xeno_api_key="test-key",
    )
    photo = result.evidence[0]
    assert photo.status == "unavailable"
    assert "display_url" not in photo.summary


def test_arizona_labels_require_returned_candidate_geography() -> None:
    wrong_country = _gbif_occurrence(
        "Sialia mexicana",
        1,
        [_gbif_media(identifier="https://images.inaturalist.org/wrong-country.jpg")],
    )
    wrong_country["countryCode"] = "MX"
    wrong_country["country"] = "Mexico"
    wrong_state = _gbif_occurrence(
        "Sialia mexicana",
        2,
        [_gbif_media(identifier="https://images.inaturalist.org/wrong-state.jpg")],
    )
    wrong_state["stateProvince"] = "New Mexico"
    conflicting_country = _gbif_occurrence(
        "Sialia mexicana",
        3,
        [_gbif_media(identifier="https://images.inaturalist.org/conflict.jpg")],
    )
    conflicting_country["country"] = "Mexico"
    valid = _gbif_occurrence(
        "Sialia mexicana",
        4,
        [_gbif_media(identifier="https://images.inaturalist.org/arizona.jpg")],
    )
    valid["country"] = "United States of America"

    queries: list[str] = []

    def xeno(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        query = str(params["query"])
        queries.append(query)
        if 'loc:"Arizona"' in query:
            return {
                "recordings": [
                    _xeno_recording("Sialia mexicana", 10, country="Mexico", locality="Sonora"),
                    _xeno_recording("Sialia mexicana", 11, locality="Albuquerque, New Mexico"),
                ]
            }
        return {
            "recordings": [
                _xeno_recording("Sialia mexicana", 10, country="Mexico", locality="Sonora")
            ]
        }

    result = enrich_recommendation_media(
        [Recommendation("rec", "Sialia mexicana")],
        gbif_getter=lambda endpoint, params: {
            "results": [wrong_country, wrong_state, conflicting_country, valid]
        },
        xeno_getter=xeno,
        xeno_api_key="test-key",
    )
    assert result.evidence[0].source_record_id == "4"
    assert result.evidence[0].summary["geographic_scope"] == "Arizona"
    assert len(queries) == 2
    assert result.evidence[1].source_record_id == "10"
    assert result.evidence[1].summary["geographic_scope"] == "Global example"

    local = enrich_recommendation_media(
        [Recommendation("rec-local", "Sialia mexicana")],
        gbif_getter=lambda endpoint, params: {"results": []},
        xeno_getter=lambda endpoint, params: {
            "recordings": [
                _xeno_recording("Sialia mexicana", 12, locality="Madera Canyon, Arizona")
            ]
        },
        xeno_api_key="test-key",
    )
    assert local.evidence[1].summary["geographic_scope"] == "Arizona"


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
            gbif_getter=lambda endpoint, params: {"results": []},
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
            gbif_getter=lambda endpoint, params: {"results": []},
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
        gbif_getter=lambda endpoint, params: {"results": []},
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
        gbif_getter=timeout,
        xeno_getter=global_only,
        xeno_api_key="test-key",
    )
    assert [row.status for row in partial.evidence] == ["unavailable", "available"]

    unavailable = enrich_recommendation_media(
        [
            Recommendation("rec-timeout", "Anser rossii"),
            Recommendation("rec-no-name", None),
        ],
        gbif_getter=timeout,
        xeno_getter=lambda endpoint, params: {"unexpected": []},
        xeno_api_key="test-key",
    )
    assert len(unavailable.evidence) == 4
    assert all(row.status == "unavailable" for row in unavailable.evidence)
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
        gbif_getter=lambda endpoint, params: {"results": []},
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

    def gbif_getter(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        return {
            "results": [
                _gbif_occurrence(
                    "Sialia mexicana",
                    42,
                    [_gbif_media(identifier="https://images.inaturalist.org/selective.jpg")],
                )
            ]
        }

    result = enrich_recommendation_media(
        [recommendation],
        gbif_getter=gbif_getter,
        xeno_getter=lambda *_: (_ for _ in ()).throw(AssertionError("unexpected Xeno lookup")),
        xeno_api_key="test-key",
        evidence_types=frozenset({"recommendation_photo"}),
    )
    assert [row.evidence_type for row in result.evidence] == ["recommendation_photo"]
    assert result.lookup_count == 1


def test_exact_gbif_http_creative_commons_license_is_canonicalized_to_https() -> None:
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
        recommendation_media._get_json(GBIF_OCCURRENCE_SEARCH, {"limit": MAX_CANDIDATES})
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
        gbif_getter=lambda endpoint, params: {"results": []},
        xeno_getter=must_not_call,
        xeno_api_key="",
    )
    assert calls == 0
    assert result.lookup_count == 1
    assert result.evidence[1].status == "unavailable"
    assert result.evidence[1].caveats == ["Xeno-canto call lookup is not configured"]
