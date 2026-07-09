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


def test_client_uses_fixed_host_model_and_output_bound_without_repr_secrets() -> None:
    observed: dict[str, object] = {}

    def post(url: str, **kwargs: object) -> httpx.Response:
        observed.update(url=url, **kwargs)
        return _response()

    client = _client(post)
    result = client.synthesize(_request())

    assert client.model == CLOUDFLARE_WORKERS_AI_MODEL
    assert observed["url"] == (
        "https://api.cloudflare.com/client/v4/accounts/account-123/ai/v1/chat/completions"
    )
    payload = observed["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == CLOUDFLARE_WORKERS_AI_MODEL
    assert payload["max_tokens"] == MAX_MODEL_OUTPUT_TOKENS
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
    with pytest.raises(CloudflareConfigurationError, match="Only @cf/zai-org/glm-4.7-flash"):
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
