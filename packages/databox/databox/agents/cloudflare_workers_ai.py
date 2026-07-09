"""Replaceable Cloudflare Workers AI client for bounded trip-plan decisions."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from databox.config.settings import DataboxSettings

CLOUDFLARE_WORKERS_AI_MODEL = "@cf/zai-org/glm-5.2"
MAX_MODEL_INPUT_BYTES = 65_536
MAX_MODEL_OUTPUT_BYTES = 32_768
MAX_MODEL_OUTPUT_TOKENS = 750
PlanActionId = Literal[
    "listen_first",
    "scan_habitat_edges",
    "move_if_quiet",
    "check_weather",
    "respect_access",
    "review_call_examples",
]
_ALLOWED_ACTION_IDS = {
    "listen_first",
    "scan_habitat_edges",
    "move_if_quiet",
    "check_weather",
    "respect_access",
    "review_call_examples",
}
_GROUNDED_SYNTHESIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action_ids": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "uniqueItems": True,
            "items": {"type": "string", "enum": sorted(_ALLOWED_ACTION_IDS)},
        },
        "grounding": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "requested_location": {"type": "string", "minLength": 1, "maxLength": 300},
                "window_start": {"type": "string", "minLength": 1, "maxLength": 64},
                "window_end": {"type": "string", "minLength": 1, "maxLength": 64},
                "duration_minutes": {"type": "integer", "minimum": 1, "maximum": 1440},
                "recommendation_ids": {
                    "type": "array",
                    "maxItems": 100,
                    "items": {"type": "string"},
                },
                "caveats": {
                    "type": "array",
                    "maxItems": 50,
                    "items": {"type": "string", "maxLength": 1000},
                },
            },
            "required": [
                "requested_location",
                "window_start",
                "window_end",
                "duration_minutes",
                "recommendation_ids",
                "caveats",
            ],
        },
    },
    "required": ["action_ids", "grounding"],
}


class CloudflareWorkersAIError(RuntimeError):
    """Safe user-facing base error; messages never include secrets or response bodies."""

    code = "cloudflare_error"
    tool_trace: Any | None = None


class CloudflareConfigurationError(CloudflareWorkersAIError):
    code = "missing_configuration"


class CloudflareAuthenticationError(CloudflareWorkersAIError):
    code = "authentication_failed"


class CloudflareRateLimitError(CloudflareWorkersAIError):
    code = "rate_limited"


class CloudflareTimeoutError(CloudflareWorkersAIError):
    code = "timeout"


class CloudflareMalformedResponseError(CloudflareWorkersAIError):
    code = "malformed_response"


class CloudflareModelUnavailableError(CloudflareWorkersAIError):
    code = "model_unavailable"


class RecommendationPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(min_length=1, max_length=128)
    common_name: str | None = Field(default=None, max_length=200)
    scientific_name: str | None = Field(default=None, max_length=200)
    recommendation_group: str = Field(min_length=1, max_length=64)
    current_rationale: str = Field(min_length=1, max_length=1000)


class GroundedSynthesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_location: str = Field(min_length=1, max_length=300)
    normalized_location_name: str = Field(min_length=1, max_length=300)
    window_start: str = Field(min_length=1, max_length=64)
    window_end: str = Field(min_length=1, max_length=64)
    duration_minutes: int = Field(gt=0, le=1440)
    skill_level: str | None = Field(default=None, max_length=64)
    constraints_text: str | None = Field(default=None, max_length=1000)
    weather_summary: dict[str, Any]
    recommendations: list[RecommendationPrompt] = Field(max_length=100)
    caveats: list[str] = Field(max_length=50)
    evidence_source_counts: dict[str, int] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_bounded_payload(self) -> GroundedSynthesisRequest:
        if any(len(item) > 1000 for item in self.caveats):
            raise ValueError("caveat text exceeds the allowed size")
        if any(len(key) > 100 or value < 0 for key, value in self.evidence_source_counts.items()):
            raise ValueError("evidence source counts are invalid")
        serialized = self.model_dump_json().encode()
        if len(serialized) > MAX_MODEL_INPUT_BYTES:
            raise ValueError("model input exceeds the allowed serialized size")
        return self


class SynthesisGrounding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_location: str = Field(min_length=1, max_length=300)
    window_start: str = Field(min_length=1, max_length=64)
    window_end: str = Field(min_length=1, max_length=64)
    duration_minutes: int = Field(gt=0, le=1440)
    recommendation_ids: list[str] = Field(max_length=100)
    caveats: list[str] = Field(max_length=50)


class GroundedSynthesisResult(BaseModel):
    """Bounded model decisions; all user-facing prose is rendered deterministically."""

    model_config = ConfigDict(extra="forbid")

    action_ids: list[PlanActionId] = Field(min_length=1, max_length=6)
    grounding: SynthesisGrounding

    @model_validator(mode="after")
    def validate_actions(self) -> GroundedSynthesisResult:
        if len(set(self.action_ids)) != len(self.action_ids):
            raise ValueError("action_ids must be unique")
        return self


class TripPlanModelClient(Protocol):
    model: str

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult: ...


HttpPost = Callable[..., httpx.Response]


@dataclass(frozen=True)
class CloudflareWorkersAIClient:
    """OpenAI-compatible Workers AI client with one hard allowlisted model."""

    api_key: str = dataclass_field(repr=False)
    account_id: str = dataclass_field(repr=False)
    model_base_url: str = dataclass_field(repr=False)
    timeout_seconds: float = 30.0
    http_post: HttpPost = httpx.post
    model: str = CLOUDFLARE_WORKERS_AI_MODEL

    def __post_init__(self) -> None:
        if self.model != CLOUDFLARE_WORKERS_AI_MODEL:
            raise CloudflareConfigurationError(
                f"Only {CLOUDFLARE_WORKERS_AI_MODEL} is permitted for agent synthesis"
            )
        missing = [
            name
            for name, value in (
                ("CF_WORKERS_AI_API_KEY", self.api_key),
                ("CF_WORKERS_AI_ACCOUNT_ID", self.account_id),
                ("CF_WORKERS_AI_MODEL_BASE_URL", self.model_base_url),
            )
            if not value.strip()
        ]
        if missing:
            raise CloudflareConfigurationError(
                "Missing Cloudflare Workers AI configuration: " + ", ".join(missing)
            )
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", self.account_id):
            raise CloudflareConfigurationError("CF_WORKERS_AI_ACCOUNT_ID has an invalid shape")
        _chat_completions_endpoint(self.model_base_url, self.account_id)

    @classmethod
    def from_settings(cls, runtime_settings: DataboxSettings) -> CloudflareWorkersAIClient:
        return cls(
            api_key=runtime_settings.cf_workers_ai_api_key.get_secret_value(),
            account_id=runtime_settings.cf_workers_ai_account_id,
            model_base_url=runtime_settings.cf_workers_ai_model_base_url,
        )

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult:
        endpoint = _chat_completions_endpoint(self.model_base_url, self.account_id)
        serialized_request = request.model_dump_json()
        if len(serialized_request.encode()) > MAX_MODEL_INPUT_BYTES:
            raise CloudflareConfigurationError("Cloudflare model input exceeds the allowed size")
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "max_completion_tokens": MAX_MODEL_OUTPUT_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "grounded_trip_plan",
                    "description": "Bounded field actions and exact supplied grounding",
                    "schema": _GROUNDED_SYNTHESIS_JSON_SCHEMA,
                    "strict": True,
                },
            },
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": serialized_request},
            ],
        }
        try:
            response = self.http_post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException:
            raise CloudflareTimeoutError("Cloudflare Workers AI request timed out") from None
        except httpx.HTTPError:
            raise CloudflareModelUnavailableError(
                "Cloudflare Workers AI could not be reached"
            ) from None

        if response.status_code in {401, 403}:
            raise CloudflareAuthenticationError(
                "Cloudflare Workers AI authentication failed"
            ) from None
        if response.status_code == 429:
            raise CloudflareRateLimitError("Cloudflare Workers AI rate limit reached") from None
        if response.status_code >= 400:
            raise CloudflareModelUnavailableError(
                f"Cloudflare Workers AI model unavailable (HTTP {response.status_code})"
            ) from None

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content is not text")
            if len(content.encode()) > MAX_MODEL_OUTPUT_BYTES:
                raise ValueError("model output is too large")
            result = GroundedSynthesisResult.model_validate_json(content)
        except UnicodeDecodeError:
            raise CloudflareMalformedResponseError(
                "Cloudflare Workers AI returned an invalid structured response"
            ) from None
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
            raise CloudflareMalformedResponseError(
                "Cloudflare Workers AI returned an invalid structured response"
            ) from None

        _validate_grounding(request, result)
        return result


def _chat_completions_endpoint(base_url: str, account_id: str) -> str:
    """Return the fixed Cloudflare endpoint after validating the configured selector/URL."""

    value = base_url.strip().rstrip("/")
    if value != CLOUDFLARE_WORKERS_AI_MODEL:
        parsed = urlparse(value.replace("{account_id}", account_id))
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.cloudflare.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 443}
        ):
            raise CloudflareConfigurationError(
                "CF_WORKERS_AI_MODEL_BASE_URL must be the approved model selector or "
                "an HTTPS api.cloudflare.com URL"
            )
    return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"


def _validate_grounding(
    request: GroundedSynthesisRequest,
    result: GroundedSynthesisResult,
) -> None:
    expected_ids = [item.recommendation_id for item in request.recommendations]
    grounding = result.grounding
    if grounding.requested_location != request.requested_location:
        raise CloudflareMalformedResponseError("Model output changed the requested location")
    if grounding.window_start != request.window_start or grounding.window_end != request.window_end:
        raise CloudflareMalformedResponseError("Model output changed the requested time window")
    if grounding.duration_minutes != request.duration_minutes:
        raise CloudflareMalformedResponseError("Model output changed the requested duration")
    if grounding.recommendation_ids != expected_ids:
        raise CloudflareMalformedResponseError("Model output changed the recommendation set")
    if grounding.caveats != request.caveats:
        raise CloudflareMalformedResponseError("Model output dropped or changed evidence caveats")
    if not set(result.action_ids).issubset(_ALLOWED_ACTION_IDS):
        raise CloudflareMalformedResponseError("Model output selected an unknown action")


_SYSTEM_PROMPT = """Select bounded field-plan actions from supplied grounded evidence.
Return exactly one JSON object with this shape:
{
  "action_ids": ["listen_first"],
  "grounding": {
    "requested_location": "exact supplied value",
    "window_start": "exact supplied value",
    "window_end": "exact supplied value",
    "duration_minutes": 90,
    "recommendation_ids": ["exact supplied ids in order"],
    "caveats": ["exact supplied caveats in order"]
  }
}
Allowed action_ids are: listen_first, scan_habitat_edges, move_if_quiet,
check_weather, respect_access, review_call_examples. Choose one to six unique actions.
Do not write prose, add species, change evidence, add numbers, infer personal history,
or emit SQL/tool calls. Preserve all grounding values exactly.
"""
