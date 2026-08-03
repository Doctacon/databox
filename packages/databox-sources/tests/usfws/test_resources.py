"""Unit tests for the snapshot-oriented USFWS resources."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from databox_sources.usfws import source as usfws_module
from dlt.extract.exceptions import ResourceExtractionError


def test_source_searches_facet_and_exact_names_and_preserves_raw_rights(
    usfws_source_factory,
    usfws_transport: list[dict[str, Any]],
) -> None:
    source = usfws_source_factory()
    records = list(source.resources["image_records"])
    runs = list(source.resources["image_search_runs"])

    assert len(records) == 3
    assert runs[0]["status"] == "complete"
    assert runs[0]["record_count"] == 3
    public = next(row for row in records if row["media_id"] == "rufous-public-domain")
    assert public["discovery_method"] == "exact_common_name,species_facet"
    assert public["source_license"] == "Public Domain"
    assert public["detail_fetch_status"] == "ok"
    assert public["source_creator"] == "Alan Example/USFWS"
    assert public["source_image_medium_width"] == 650
    assert public["source_image_medium_height"] == 406
    assert public["source_image_original_width"] == 1600
    assert public["source_image_original_height"] == 1000
    assert public["source_mime_type"] == "image/jpeg"
    assert public["source_published_at"] == "2024-06-21"
    assert json.loads(public["scientific_name_tags_json"]) == ["Selasphorus rufus"]
    assert json.loads(public["subject_tags_json"]) == ["Birds", "Pollinators"]

    noncommercial = next(row for row in records if row["media_id"] == "rufous-noncommercial")
    assert noncommercial["source_license"] == "CC BY-NC 4.0"
    unsafe = next(row for row in records if row["media_id"] == "unsafe")
    assert unsafe["source_page_url"] == "https://images.example.invalid/media/unsafe"
    assert unsafe["detail_fetch_status"] == "skipped_unsafe_url"

    facet_calls = [
        call for call in usfws_transport if call["url"] == usfws_module.USFWS_IMAGE_SEARCH_URL
    ]
    global_calls = [
        call for call in usfws_transport if call["url"] == usfws_module.USFWS_GLOBAL_SEARCH_URL
    ]
    assert len(facet_calls) == 1
    assert facet_calls[0]["params"]["species"] == '["Rufous Hummingbird"]'
    assert "$keywords" not in facet_calls[0]["params"]
    assert len(global_calls) == 2
    assert {call["params"]["$keywords"] for call in global_calls} == {
        '"Rufous Hummingbird"',
        '"Selasphorus rufus"',
    }
    assert all(call["params"]["type"] == '["Image"]' for call in global_calls)
    search_calls = [*facet_calls, *global_calls]
    assert all(call["params"]["$top"] == usfws_module.USFWS_PAGE_SIZE for call in search_calls)
    assert all(call["stream"] is True for call in usfws_transport)
    assert not any("license" in call["params"] for call in search_calls)
    assert not any("images.example.invalid" in call["url"] for call in usfws_transport)


def test_missing_targets_fail_only_when_resource_is_evaluated() -> None:
    source = usfws_module.usfws_source()
    assert set(source.resources) == {"image_search_runs", "image_records"}
    with pytest.raises(ResourceExtractionError, match="target_species must be supplied"):
        list(source.resources["image_records"])


def test_source_bounds_targets_attempts_and_concurrency() -> None:
    with pytest.raises(ValueError, match="unsupported characters"):
        usfws_module.usfws_source(
            target_species=[
                {
                    "species_code": "bad code",
                    "common_name": "Rufous Hummingbird",
                    "scientific_name": "Selasphorus rufus",
                }
            ]
        )
    with pytest.raises(ValueError, match="request_max_attempts"):
        usfws_module.usfws_source(request_max_attempts=7)
    with pytest.raises(ValueError, match="detail_workers"):
        usfws_module.usfws_source(detail_workers=5)


def test_oversized_query_fails_instead_of_publishing_partial_snapshot(monkeypatch) -> None:
    class Response:
        content = json.dumps({"list": [], "_meta": {"total": 501}}).encode()
        headers = {"Content-Length": str(len(content))}

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(usfws_module, "_http_get", lambda *args, **kwargs: Response())
    source = usfws_module.usfws_source(
        target_species=[
            {
                "species_code": "rufhum",
                "common_name": "Rufous Hummingbird",
                "scientific_name": "Selasphorus rufus",
            }
        ]
    )
    with pytest.raises(ResourceExtractionError, match="full-snapshot cap"):
        list(source.resources["image_search_runs"])


def test_nonempty_search_requires_proof_that_multiselect_filter_was_applied(
    monkeypatch,
) -> None:
    class Response:
        content = json.dumps(
            {
                "list": ["<div class='teaser media-image'></div>"],
                "_meta": {
                    "total": 1,
                    "facets": {"species": [{"filter": "Another Bird", "count": 1}]},
                },
            }
        ).encode()
        headers = {"Content-Length": str(len(content))}

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(usfws_module, "_http_get", lambda *args, **kwargs: Response())
    source = usfws_module.usfws_source(
        target_species=[
            {
                "species_code": "rufhum",
                "common_name": "Rufous Hummingbird",
                "scientific_name": "Selasphorus rufus",
            }
        ]
    )
    with pytest.raises(ResourceExtractionError, match="filter was applied"):
        list(source.resources["image_search_runs"])


def test_transient_request_retries_six_times_with_exact_bounded_backoff(
    monkeypatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def unavailable(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise OSError(
            "private transport detail and token=do-not-disclose"  # secret-scan: allow
        )

    monkeypatch.setattr(usfws_module, "_http_get", unavailable)
    monkeypatch.setattr(usfws_module.time, "sleep", delays.append)

    with pytest.raises(usfws_module._RequestRetriesExhaustedError) as raised:
        usfws_module._get_with_retry(
            "https://www.fws.gov/media/example?token=do-not-disclose",  # secret-scan: allow
            max_attempts=usfws_module.USFWS_REQUEST_MAX_ATTEMPTS,
        )

    assert attempts == 6
    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]
    assert "do-not-disclose" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_declared_oversized_response_is_rejected_before_body_read(monkeypatch) -> None:
    class Response:
        status_code = 200
        headers = {"Content-Length": "11"}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, *, chunk_size: int):
            raise AssertionError(f"must not read a declared oversized body ({chunk_size})")

    monkeypatch.setattr(usfws_module, "_http_get", lambda *args, **kwargs: Response())

    with pytest.raises(usfws_module._ResponseBodyTooLargeError, match="10-byte limit"):
        usfws_module._get_with_retry(
            usfws_module.USFWS_IMAGE_SEARCH_URL,
            max_attempts=usfws_module.USFWS_REQUEST_MAX_ATTEMPTS,
            maximum_body_bytes=10,
            body_label="search",
        )


def test_chunked_response_is_stopped_at_exact_body_bound(monkeypatch) -> None:
    attempts = 0

    class Response:
        status_code = 200
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, *, chunk_size: int):
            assert chunk_size == usfws_module.USFWS_RESPONSE_CHUNK_BYTES
            yield b"a" * 10
            yield b"b"
            raise AssertionError("the reader must stop as soon as the limit is exceeded")

    def response(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        return Response()

    monkeypatch.setattr(usfws_module, "_http_get", response)

    with pytest.raises(usfws_module._ResponseBodyTooLargeError, match="10-byte limit"):
        usfws_module._get_with_retry(
            "https://www.fws.gov/media/example",
            max_attempts=usfws_module.USFWS_REQUEST_MAX_ATTEMPTS,
            maximum_body_bytes=10,
            body_label="detail",
        )

    assert attempts == 1


@pytest.mark.parametrize("content_length", ["not-a-number", "-1"])
def test_malformed_content_length_fails_without_retry(
    monkeypatch,
    content_length: str,
) -> None:
    attempts = 0

    class Response:
        status_code = 200
        headers = {"Content-Length": content_length}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, *, chunk_size: int):
            yield b"{}"

    def response(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        return Response()

    monkeypatch.setattr(usfws_module, "_http_get", response)

    with pytest.raises(usfws_module._ResponseBodyValidationError, match="Content-Length"):
        usfws_module._get_with_retry(
            usfws_module.USFWS_IMAGE_SEARCH_URL,
            max_attempts=usfws_module.USFWS_REQUEST_MAX_ATTEMPTS,
            maximum_body_bytes=10,
            body_label="search",
        )

    assert attempts == 1


@pytest.mark.parametrize(
    ("retry_after", "expected_delay"),
    [("7", 7.0), ("999999999999999999999", 30.0), ("invalid", 1.0)],
)
def test_retry_after_is_honored_but_bounded(
    monkeypatch,
    retry_after: str,
    expected_delay: float,
) -> None:
    attempts = 0
    delays: list[float] = []

    class Response:
        status_code = 503
        headers = {"Retry-After": retry_after}

        def raise_for_status(self) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("upstream detail")

    monkeypatch.setattr(usfws_module, "_http_get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(usfws_module.time, "sleep", delays.append)

    usfws_module._get_with_retry(
        "https://www.fws.gov/media/example",
        max_attempts=usfws_module.USFWS_REQUEST_MAX_ATTEMPTS,
    )

    assert attempts == 2
    assert delays == [expected_delay]


def test_http_date_retry_after_is_parsed_and_bounded() -> None:
    class Response:
        headers = {"Retry-After": "Mon, 03 Aug 2026 12:00:20 GMT"}

    assert (
        usfws_module._retry_after_seconds(Response(), now=datetime(2026, 8, 3, 12, 0, tzinfo=UTC))
        == 20.0
    )

    Response.headers["Retry-After"] = "Mon, 03 Aug 2026 12:02:00 GMT"
    assert (
        usfws_module._retry_after_seconds(Response(), now=datetime(2026, 8, 3, 12, 0, tzinfo=UTC))
        == 30.0
    )


def test_non_retriable_http_failure_is_secret_safe_and_not_retried(monkeypatch) -> None:
    attempts = 0
    delays: list[float] = []

    class Response:
        status_code = 404
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            raise RuntimeError(
                "private response and token=do-not-disclose"  # secret-scan: allow
            )

    def unavailable(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        return Response()

    monkeypatch.setattr(usfws_module, "_http_get", unavailable)
    monkeypatch.setattr(usfws_module.time, "sleep", delays.append)

    with pytest.raises(RuntimeError, match="non-retriable HTTP status 404") as raised:
        usfws_module._get_with_retry(
            "https://www.fws.gov/media/example?token=do-not-disclose",  # secret-scan: allow
            max_attempts=usfws_module.USFWS_REQUEST_MAX_ATTEMPTS,
        )

    assert attempts == 1
    assert delays == []
    assert "do-not-disclose" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_exhausted_detail_is_retained_as_ineligible_without_aborting_snapshot(
    usfws_source_factory,
    usfws_transport,
    monkeypatch,
) -> None:
    fixture_get = usfws_module._http_get
    unavailable_attempts = 0
    delays: list[float] = []

    class UnavailableResponse:
        status_code = 503
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            raise RuntimeError("temporary upstream outage")

    def partly_unavailable(url: str, **kwargs: Any):
        nonlocal unavailable_attempts
        if url.endswith("/media/rufous-noncommercial"):
            unavailable_attempts += 1
            return UnavailableResponse()
        return fixture_get(url, **kwargs)

    monkeypatch.setattr(usfws_module, "_http_get", partly_unavailable)
    monkeypatch.setattr(usfws_module.time, "sleep", delays.append)

    source = usfws_source_factory()
    records = list(source.resources["image_records"])
    runs = list(source.resources["image_search_runs"])

    unavailable = next(row for row in records if row["media_id"] == "rufous-noncommercial")
    assert unavailable["detail_fetch_status"] == "unavailable_after_retries"
    assert json.loads(unavailable["scientific_name_tags_json"]) == []
    assert json.loads(unavailable["species_tag_urls_json"]) == []
    assert json.loads(unavailable["subject_tags_json"]) == []
    assert "source_license" not in unavailable
    assert unavailable_attempts == 6
    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]
    assert runs[0]["status"] == "complete"
    assert runs[0]["record_count"] == 3


def test_exhausted_search_still_aborts_complete_snapshot(monkeypatch) -> None:
    attempts = 0
    delays: list[float] = []

    class Response:
        status_code = 503
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            raise RuntimeError("temporary upstream outage")

    def unavailable(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        return Response()

    monkeypatch.setattr(usfws_module, "_http_get", unavailable)
    monkeypatch.setattr(usfws_module.time, "sleep", delays.append)
    source = usfws_module.usfws_source(
        target_species=[
            {
                "species_code": "rufhum",
                "common_name": "Rufous Hummingbird",
                "scientific_name": "Selasphorus rufus",
            }
        ]
    )

    with pytest.raises(ResourceExtractionError, match="failed after 6 attempts"):
        list(source.resources["image_search_runs"])

    assert attempts == 6
    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]


def test_systemic_detail_outage_aborts_above_reviewed_unavailable_cap(monkeypatch) -> None:
    candidates = [
        usfws_module._SearchCandidate(
            page_href=f"/media/unavailable-{index}",
            source_page_url=f"https://www.fws.gov/media/unavailable-{index}",
            media_id=f"unavailable-{index}",
            title=f"Unavailable {index}",
            caption=None,
            credit=None,
            image_url=None,
            alt_text=None,
            width=None,
            height=None,
            published_at=None,
            mime_label=None,
        )
        for index in range(usfws_module.USFWS_MAX_UNAVAILABLE_DETAILS + 1)
    ]
    monkeypatch.setattr(usfws_module, "_fetch_search", lambda *args, **kwargs: candidates)

    def unavailable(*args, **kwargs):
        raise usfws_module._RequestRetriesExhaustedError(
            "USFWS transient request failed after 6 attempts"
        )

    monkeypatch.setattr(usfws_module, "_get_with_retry", unavailable)
    source = usfws_module.usfws_source(
        target_species=[
            {
                "species_code": "rufhum",
                "common_name": "Rufous Hummingbird",
                "scientific_name": "Selasphorus rufus",
            }
        ],
        detail_workers=1,
    )

    with pytest.raises(ResourceExtractionError, match="unavailable detail-page cap of 10"):
        list(source.resources["image_search_runs"])


@pytest.mark.parametrize(
    ("cap_name", "error_match"),
    [
        ("USFWS_MAX_TOTAL_CANDIDATES", "global candidate cap"),
        ("USFWS_MAX_DETAIL_PAGES", "detail-page cap"),
    ],
)
def test_global_candidate_and_detail_caps_fail_before_any_detail_fetch(
    monkeypatch,
    cap_name: str,
    error_match: str,
) -> None:
    candidates = [
        usfws_module._SearchCandidate(
            page_href=f"/media/candidate-{index}",
            source_page_url=f"https://www.fws.gov/media/candidate-{index}",
            media_id=f"candidate-{index}",
            title=f"Candidate {index}",
            caption=None,
            credit=None,
            image_url=None,
            alt_text=None,
            width=None,
            height=None,
            published_at=None,
            mime_label=None,
        )
        for index in range(3)
    ]
    monkeypatch.setattr(usfws_module, cap_name, 2)
    monkeypatch.setattr(usfws_module, "_fetch_search", lambda *args, **kwargs: candidates)

    def unexpected_detail_fetch(*args, **kwargs):
        raise AssertionError("detail fetch must not start above the global candidate cap")

    monkeypatch.setattr(usfws_module, "_get_with_retry", unexpected_detail_fetch)
    source = usfws_module.usfws_source(
        target_species=[
            {
                "species_code": "rufhum",
                "common_name": "Rufous Hummingbird",
                "scientific_name": "Selasphorus rufus",
            }
        ]
    )
    with pytest.raises(ResourceExtractionError, match=error_match):
        list(source.resources["image_search_runs"])


def test_short_later_page_fails_instead_of_publishing_complete_marker(monkeypatch) -> None:
    card = """
    <div class="teaser media-image">
      <div class="field--name-name"><a href="/media/one">One</a></div>
    </div>
    """

    class Response:
        def __init__(self, fragments: list[str]) -> None:
            self.content = json.dumps(
                {
                    "list": fragments,
                    "_meta": {
                        "total": 2,
                        "facets": {
                            "species": [{"filter": "Rufous Hummingbird", "count": 2}],
                            "type": [{"filter": "Image", "count": 2}],
                        },
                    },
                }
            ).encode()
            self.headers = {"Content-Length": str(len(self.content))}

        def raise_for_status(self) -> None:
            return None

    def fake_get(*args, **kwargs) -> Response:
        params = kwargs.get("params") or {}
        return Response([card] if params.get("$skip") == 0 else [])

    monkeypatch.setattr(usfws_module, "_http_get", fake_get)
    source = usfws_module.usfws_source(
        target_species=[
            {
                "species_code": "rufhum",
                "common_name": "Rufous Hummingbird",
                "scientific_name": "Selasphorus rufus",
            }
        ]
    )
    with pytest.raises(ResourceExtractionError, match="ended before its declared total"):
        list(source.resources["image_search_runs"])


def test_media_mime_is_inferred_from_published_medium_url() -> None:
    detail = """
    <div class="media-full-content image">
      <a class="photoswipe"
         href="https://www.fws.gov/sites/default/files/images/original.png"
         data-pswp-width="1600" data-pswp-height="1000"></a>
      <a href="https://www.fws.gov/sites/default/files/images/medium.jpg"
         download="usfws-medium">Medium (650 x 406)</a>
      <div class="media-type">Image</div>
    </div>
    """
    parsed = usfws_module.parse_media_page(detail)
    assert parsed["source_image_medium_url"].endswith("medium.jpg")
    assert parsed["source_image_original_url"].endswith("original.png")
    assert parsed["source_mime_type"] == "image/jpeg"


def test_multiple_rights_items_are_preserved_and_marked_ambiguous() -> None:
    detail = """
    <div class="media-full-content image">
      <div class="field field--name-field-creative-commons-license">
        <div class="field--item">
          <a href="/notices">Public Domain</a>
        </div>
        <div class="field--item">
          <a href="https://creativecommons.org/licenses/by-nc/4.0/">CC BY-NC 4.0</a>
        </div>
      </div>
      <div class="media-type">Image</div>
    </div>
    """
    parsed = usfws_module.parse_media_page(detail)

    assert parsed["detail_fetch_status"] == "ambiguous_rights"
    assert json.loads(parsed["source_license"]) == ["Public Domain", "CC BY-NC 4.0"]
    assert json.loads(parsed["source_license_url"]) == [
        "https://www.fws.gov/notices",
        "https://creativecommons.org/licenses/by-nc/4.0/",
    ]
