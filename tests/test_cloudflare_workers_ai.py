"""Cloudflare Workers AI model-boundary tests; no live requests."""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable

import httpx
import pytest
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    MAX_MODEL_OUTPUT_TOKENS,
    CloudflareAuthenticationError,
    CloudflareConfigurationError,
    CloudflareMalformedResponseError,
    CloudflareModelUnavailableError,
    CloudflareRateLimitError,
    CloudflareTimeoutError,
    CloudflareWorkersAIClient,
    CloudflareWorkersAIError,
    GroundedSynthesisRequest,
    TargetSynthesisRequest,
    WatchClusterPrompt,
    WatchReportSynthesisGrounding,
    WatchReportSynthesisRequest,
    WatchReportSynthesisResult,
)
from databox.config.settings import DataboxSettings
from pydantic import ValidationError

API_KEY = "test-secret-that-must-not-appear"


def _request(**overrides: object) -> GroundedSynthesisRequest:
    value: dict[str, object] = {
        "requested_location": "Thumb Butte",
        "normalized_location_name": "Thumb Butte, Prescott, AZ",
        "window_start": "2026-07-09T06:00:00",
        "window_end": "2026-07-09T07:30:00",
        "duration_minutes": 90,
        "skill_level": "beginner",
        "constraints_text": "focus on calls",
        "weather_summary": {"status": "available", "elevation_m": 1642},
        "recommendations": [
            {
                "recommendation_id": "rec-1",
                "common_name": "Mexican Jay",
                "scientific_name": "Aphelocoma wollweberi",
                "recommendation_group": "high_likelihood",
                "current_rationale": "Recent observations support this target.",
            }
        ],
        "caveats": ["Weather changes quickly"],
        "evidence_source_counts": {"ebird": 2, "open_meteo": 1},
    }
    value.update(overrides)
    return GroundedSynthesisRequest.model_validate(value)


def _model_content(**overrides: object) -> str:
    value: dict[str, object] = {
        "action_ids": ["listen_first", "scan_habitat_edges"],
        "grounding": {
            "requested_location": "Thumb Butte",
            "window_start": "2026-07-09T06:00:00",
            "window_end": "2026-07-09T07:30:00",
            "duration_minutes": 90,
            "recommendation_ids": ["rec-1"],
            "caveats": ["Weather changes quickly"],
        },
    }
    value.update(overrides)
    return json.dumps(value)


def _response(status: int = 200, *, content: str | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        json={"choices": [{"message": {"content": content or _model_content()}}]},
        request=httpx.Request("POST", "https://api.cloudflare.com"),
    )


def _client(post: Callable[..., httpx.Response]) -> CloudflareWorkersAIClient:
    return CloudflareWorkersAIClient(
        api_key=API_KEY,
        account_id="account-123",
        model_base_url="https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        http_post=post,
    )


def _target_request() -> TargetSynthesisRequest:
    return TargetSynthesisRequest.model_validate(
        {
            "species_code": "target1",
            "common_name": "Target Bird",
            "scientific_name": "Avis target",
            "taxonomic_category": "species",
            "origin": {
                "requested_location": "Prescott",
                "normalized_location_name": "Prescott, AZ",
                "latitude": 34.0,
                "longitude": -112.0,
                "timezone": "America/Phoenix",
                "region_code": "US-AZ",
            },
            "window_start": "2026-07-11T06:00:00",
            "window_end": "2026-07-11T08:00:00",
            "duration_minutes": 120,
            "radius_miles": 25,
            "evidence_freshness_at": "2026-07-10T08:00:00",
            "weather": {
                "status": "available",
                "retrieved_at": "2026-07-10T09:00:00Z",
                "forecast_summary": {
                    "temperature_2m_min": 19.0,
                    "temperature_2m_max": 21.0,
                    "temperature_2m_avg": 20.0,
                    "relative_humidity_2m_avg": 39.0,
                    "precipitation_probability_max": 0.0,
                    "precipitation_sum": 0.0,
                    "wind_speed_10m_max": 7.0,
                    "wind_gusts_10m_max": 10.0,
                    "weather_codes": [0],
                },
                "units": {
                    "temperature": "°C",
                    "relative_humidity": "%",
                    "precipitation_probability": "%",
                    "precipitation": "mm",
                    "wind_speed": "km/h",
                    "wind_gusts": "km/h",
                    "elevation": "m",
                },
                "elevation_m": 330.0,
                "caveats": [],
            },
            "candidates": [
                {
                    "location_id": "L1",
                    "location_name": "Public Lake",
                    "latitude": 34.1,
                    "longitude": -112.1,
                    "observation_count": 2,
                    "latest_observation_at": "2026-07-10T07:00:00",
                    "distance_km": 6.759,
                    "distance_miles": 4.2,
                    "evidence_loaded_at": "2026-07-10T08:00:00",
                }
            ],
            "caveats": ["Recent evidence is not a guarantee."],
        }
    )


def _target_content(*, species_code: str = "target1", evidence_hash: str | None = None) -> str:
    request = _target_request()
    return json.dumps(
        {
            "action_ids": ["try_top_location", "verify_access"],
            "grounding": {
                "species_code": species_code,
                "requested_location": request.origin.requested_location,
                "window_start": request.window_start,
                "window_end": request.window_end,
                "duration_minutes": request.duration_minutes,
                "radius_miles": request.radius_miles,
                "candidate_ids": ["L1"],
                "evidence_freshness_at": request.evidence_freshness_at,
                "weather_status": request.weather.status,
                "evidence_hash": evidence_hash or request.evidence_hash,
                "caveats": request.caveats,
            },
        }
    )


def _watch_request() -> WatchReportSynthesisRequest:
    target = _target_request()
    return WatchReportSynthesisRequest(
        species_code="target1",
        common_name="Target Bird",
        scientific_name="Avis target",
        confirmed_location=WatchClusterPrompt(
            location_id="L1",
            location_name="Public Lake",
            latitude=34.1,
            longitude=-112.1,
            independent_submission_count=2,
            latest_observation_at="2026-07-10T14:00:00+00:00",
            distance_km=6.759,
            distance_miles=4.2,
            evidence_loaded_at="2026-07-10T14:05:00+00:00",
        ),
        morning_start="2026-07-11T11:30:00+00:00",
        morning_end="2026-07-11T13:30:00+00:00",
        event_horizon_end="2026-07-15T12:00:00+00:00",
        evidence_freshness_at="2026-07-10T14:00:00+00:00",
        weather=target.weather,
        caveats=["Recent evidence is not a guarantee."],
    )


def _watch_content(request: WatchReportSynthesisRequest, *, fact_hash: str | None = None) -> str:
    return WatchReportSynthesisResult(
        emphasis_ids=["freshness", "confirmed_location", "weather"],
        grounding=WatchReportSynthesisGrounding(
            species_code=request.species_code,
            fact_hash=fact_hash or request.fact_hash,
        ),
    ).model_dump_json()


def test_watch_report_client_uses_strict_schema_and_exact_fact_hash() -> None:
    observed: dict[str, object] = {}
    request = _watch_request()

    def post(url: str, **kwargs: object) -> httpx.Response:
        observed.update(url=url, **kwargs)
        return _response(content=_watch_content(request))

    result = _client(post).synthesize_watch_report(request)
    payload = observed["json"]
    assert isinstance(payload, dict)
    assert payload["response_format"]["json_schema"]["name"] == "grounded_watch_report"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert (
        payload["response_format"]["json_schema"]["schema"]["properties"]["emphasis_ids"][
            "uniqueItems"
        ]
        is True
    )
    prompt = payload["messages"][1]["content"]
    assert "Public Lake" in prompt
    assert request.fact_hash in prompt
    assert "Synthetic Center" not in prompt
    assert '"watch_center"' not in prompt
    request_properties = WatchReportSynthesisRequest.model_json_schema()["properties"]
    assert "confirmed_location" in request_properties
    assert "watch_center" not in request_properties
    assert "clusters" not in request_properties
    assert result.emphasis_ids == ["freshness", "confirmed_location", "weather"]


def test_watch_report_request_rejects_inconsistent_grounded_facts() -> None:
    base = _watch_request().model_dump(exclude={"fact_hash"})
    personal = dict(base)
    personal["watch_center"] = {
        "name": "Personal Home",
        "latitude": 33.123,
        "longitude": -112.456,
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WatchReportSynthesisRequest.model_validate(personal)

    stale = dict(base)
    stale["evidence_freshness_at"] = "2026-07-10T13:00:00+00:00"
    with pytest.raises(ValidationError, match="evidence freshness"):
        WatchReportSynthesisRequest.model_validate(stale)

    wrong_window = dict(base)
    wrong_window["morning_end"] = "2026-07-11T14:00:00+00:00"
    with pytest.raises(ValidationError, match="morning window"):
        WatchReportSynthesisRequest.model_validate(wrong_window)


def test_watch_report_client_rejects_changed_fact_hash() -> None:
    request = _watch_request()

    def post(*args: object, **kwargs: object) -> httpx.Response:
        return _response(content=_watch_content(request, fact_hash="0" * 64))

    with pytest.raises(CloudflareMalformedResponseError, match="watch report facts"):
        _client(post).synthesize_watch_report(request)


def test_target_client_uses_strict_schema_and_exact_grounding() -> None:
    observed: dict[str, object] = {}

    def post(url: str, **kwargs: object) -> httpx.Response:
        observed.update(url=url, **kwargs)
        return _response(content=_target_content())

    result = _client(post).synthesize_target(_target_request())
    payload = observed["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == CLOUDFLARE_WORKERS_AI_MODEL
    schema_config = payload["response_format"]["json_schema"]
    assert schema_config["name"] == "grounded_target_plan"
    assert schema_config["strict"] is True
    assert schema_config["schema"]["additionalProperties"] is False
    serialized_request = payload["messages"][1]["content"]
    assert "Public Lake" in serialized_request
    assert "temperature_2m_avg" in serialized_request
    assert _target_request().evidence_hash in serialized_request
    assert result.action_ids == ["try_top_location", "verify_access"]


def test_target_client_rejects_changed_grounding() -> None:
    def post(*args: object, **kwargs: object) -> httpx.Response:
        return _response(content=_target_content(species_code="changed"))

    with pytest.raises(CloudflareMalformedResponseError, match="target species"):
        _client(post).synthesize_target(_target_request())


def test_target_client_rejects_changed_evidence_hash() -> None:
    def post(*args: object, **kwargs: object) -> httpx.Response:
        return _response(content=_target_content(evidence_hash="0" * 64))

    with pytest.raises(CloudflareMalformedResponseError, match="supplied evidence"):
        _client(post).synthesize_target(_target_request())


def test_client_uses_fixed_host_model_and_output_bound_without_repr_secrets() -> None:
    observed: dict[str, object] = {}

    def post(url: str, **kwargs: object) -> httpx.Response:
        observed.update(url=url, **kwargs)
        return _response()

    client = _client(post)
    result = client.synthesize(_request())

    assert CLOUDFLARE_WORKERS_AI_MODEL == "@cf/zai-org/glm-5.2"
    assert client.model == CLOUDFLARE_WORKERS_AI_MODEL
    assert observed["url"] == (
        "https://api.cloudflare.com/client/v4/accounts/account-123/ai/v1/chat/completions"
    )
    payload = observed["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == CLOUDFLARE_WORKERS_AI_MODEL
    assert payload["max_completion_tokens"] == MAX_MODEL_OUTPUT_TOKENS
    assert "max_tokens" not in payload
    response_format = payload["response_format"]
    assert response_format["type"] == "json_schema"
    json_schema = response_format["json_schema"]
    assert json_schema["name"] == "grounded_trip_plan"
    assert json_schema["strict"] is True
    schema = json_schema["schema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["grounding"]["additionalProperties"] is False
    assert schema["properties"]["action_ids"]["uniqueItems"] is True
    assert set(schema["properties"]["action_ids"]["items"]["enum"]) == {
        "listen_first",
        "scan_habitat_edges",
        "move_if_quiet",
        "check_weather",
        "respect_access",
        "review_call_examples",
    }
    assert API_KEY not in repr(client)
    assert "account-123" not in repr(client)
    assert "api.cloudflare.com" not in repr(client)
    assert result.action_ids == ["listen_first", "scan_habitat_edges"]


def test_allowlisted_model_selector_derives_official_endpoint() -> None:
    observed: dict[str, object] = {}

    def post(url: str, **kwargs: object) -> httpx.Response:
        observed.update(url=url, **kwargs)
        return _response()

    client = CloudflareWorkersAIClient(
        api_key=API_KEY,
        account_id="account-123",
        model_base_url=CLOUDFLARE_WORKERS_AI_MODEL,
        http_post=post,
    )
    client.synthesize(_request())
    assert observed["url"] == (
        "https://api.cloudflare.com/client/v4/accounts/account-123/ai/v1/chat/completions"
    )


@pytest.mark.parametrize(
    "value",
    [
        "http://api.cloudflare.com/client/v4",
        "https://example.com/client/v4",
        "@cf/another/model",
        "https://api.cloudflare.com.evil.example/client/v4",
    ],
)
def test_client_rejects_non_cloudflare_or_plain_http_credential_targets(value: str) -> None:
    with pytest.raises(CloudflareConfigurationError):
        CloudflareWorkersAIClient(
            api_key=API_KEY,
            account_id="account-123",
            model_base_url=value,
        )


def test_client_from_typed_settings_and_missing_configuration() -> None:
    configured = DataboxSettings(
        _env_file=None,
        CF_WORKERS_AI_API_KEY=API_KEY,
        CF_WORKERS_AI_ACCOUNT_ID="account-123",
        CF_WORKERS_AI_MODEL_BASE_URL=CLOUDFLARE_WORKERS_AI_MODEL,
    )
    client = CloudflareWorkersAIClient.from_settings(configured)
    assert client.account_id == "account-123"
    assert API_KEY not in repr(configured)

    missing = DataboxSettings(
        _env_file=None,
        CF_WORKERS_AI_API_KEY="",
        CF_WORKERS_AI_ACCOUNT_ID="",
        CF_WORKERS_AI_MODEL_BASE_URL="",
    )
    with pytest.raises(CloudflareConfigurationError, match="Missing Cloudflare"):
        CloudflareWorkersAIClient.from_settings(missing)


def test_client_rejects_any_other_model() -> None:
    with pytest.raises(CloudflareConfigurationError, match="Only @cf/zai-org/glm-5.2"):
        CloudflareWorkersAIClient(
            api_key="x",
            account_id="a",
            model_base_url=CLOUDFLARE_WORKERS_AI_MODEL,
            model="another-model",
        )


@pytest.mark.parametrize(
    ("status", "error_type", "code"),
    [
        (401, CloudflareAuthenticationError, "authentication_failed"),
        (403, CloudflareAuthenticationError, "authentication_failed"),
        (429, CloudflareRateLimitError, "rate_limited"),
        (404, CloudflareModelUnavailableError, "model_unavailable"),
        (500, CloudflareModelUnavailableError, "model_unavailable"),
    ],
)
def test_client_maps_http_failures_without_response_body(
    status: int,
    error_type: type[CloudflareWorkersAIError],
    code: str,
) -> None:
    client = _client(lambda *args, **kwargs: _response(status, content="sensitive-response"))
    with pytest.raises(error_type) as exc_info:
        client.synthesize(_request())
    rendered = "".join(traceback.format_exception(exc_info.value))
    assert exc_info.value.code == code
    assert API_KEY not in rendered
    assert "sensitive-response" not in rendered


def test_client_suppresses_transport_details_from_formatted_traceback() -> None:
    def timeout(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ReadTimeout("secret transport detail")

    with pytest.raises(CloudflareTimeoutError) as exc_info:
        _client(timeout).synthesize(_request())
    rendered = "".join(traceback.format_exception(exc_info.value))
    assert "secret transport detail" not in rendered
    assert "ReadTimeout" not in rendered


def test_client_suppresses_invalid_utf8_response_details_from_formatted_traceback() -> None:
    unsafe_response_bytes = b'{"detail":"private-response-\xff-bytes"}'

    def invalid_utf8(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            content=unsafe_response_bytes,
            request=httpx.Request("POST", "https://api.cloudflare.com"),
        )

    with pytest.raises(CloudflareMalformedResponseError) as exc_info:
        _client(invalid_utf8).synthesize(_request())

    rendered = "".join(traceback.format_exception(exc_info.value))
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert "private-response" not in rendered
    assert repr(unsafe_response_bytes) not in rendered
    assert "UnicodeDecodeError" not in rendered


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        _model_content(action_ids=["listen_first", "listen_first"]),
        _model_content(
            grounding={
                "requested_location": "Thumb Butte",
                "window_start": "2026-07-09T06:00:00",
                "window_end": "2026-07-09T09:30:00",
                "duration_minutes": 90,
                "recommendation_ids": ["rec-1"],
                "caveats": ["Weather changes quickly"],
            }
        ),
        json.dumps(
            {
                "action_ids": ["listen_first"],
                "field_plan_text": "Invented Bald Eagle evidence",
                "grounding": {
                    "requested_location": "Thumb Butte",
                    "window_start": "2026-07-09T06:00:00",
                    "window_end": "2026-07-09T07:30:00",
                    "duration_minutes": 90,
                    "recommendation_ids": ["rec-1"],
                    "caveats": ["Weather changes quickly"],
                },
            }
        ),
    ],
)
def test_client_rejects_malformed_or_ungrounded_output(content: str) -> None:
    with pytest.raises(CloudflareMalformedResponseError):
        _client(lambda *args, **kwargs: _response(content=content)).synthesize(_request())


def test_request_bounds_reject_large_collections_strings_and_payloads() -> None:
    with pytest.raises(ValidationError):
        _request(caveats=["x"] * 51)
    with pytest.raises(ValidationError):
        _request(constraints_text="x" * 1001)
    with pytest.raises(ValidationError):
        _request(weather_summary={"payload": "x" * 70_000})
