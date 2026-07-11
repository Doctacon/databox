"""Replaceable Cloudflare Workers AI client for bounded trip-plan decisions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

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
TargetActionId = Literal[
    "try_top_location",
    "arrive_early",
    "review_freshness",
    "check_weather",
    "verify_access",
]
_ALLOWED_TARGET_ACTION_IDS = {
    "try_top_location",
    "arrive_early",
    "review_freshness",
    "check_weather",
    "verify_access",
}
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


def _bounded_timestamp(value: str) -> str:
    if not value or len(value) > 64:
        raise ValueError("timestamp has an invalid size")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp is invalid") from None
    return value


class TargetOriginPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    requested_location: str = Field(min_length=1, max_length=300)
    normalized_location_name: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(min_length=1, max_length=64)
    region_code: Literal["US-AZ"]


class TargetLocationPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    location_id: str = Field(min_length=1, max_length=128)
    location_name: str | None = Field(default=None, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observation_count: int = Field(ge=1)
    latest_observation_at: str = Field(min_length=1, max_length=64)
    distance_km: float = Field(ge=0, le=483)
    distance_miles: float = Field(ge=0, le=300)
    evidence_loaded_at: str | None = Field(default=None, max_length=64)

    _latest_timestamp = field_validator("latest_observation_at")(_bounded_timestamp)

    @field_validator("evidence_loaded_at")
    @classmethod
    def validate_optional_timestamp(cls, value: str | None) -> str | None:
        return _bounded_timestamp(value) if value is not None else None


class TargetWeatherSummaryPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    temperature_2m_min: float | None
    temperature_2m_max: float | None
    temperature_2m_avg: float | None
    relative_humidity_2m_avg: float | None
    precipitation_probability_max: float | None
    precipitation_sum: float | None
    wind_speed_10m_max: float | None
    wind_gusts_10m_max: float | None
    weather_codes: list[int] = Field(max_length=100)


class TargetWeatherUnitsPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: str = Field(min_length=1, max_length=32)
    relative_humidity: str = Field(min_length=1, max_length=32)
    precipitation_probability: str = Field(min_length=1, max_length=32)
    precipitation: str = Field(min_length=1, max_length=32)
    wind_speed: str = Field(min_length=1, max_length=32)
    wind_gusts: str = Field(min_length=1, max_length=32)
    elevation: str = Field(min_length=1, max_length=32)


class TargetWeatherPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    status: Literal["available", "partial", "unavailable"]
    retrieved_at: str = Field(min_length=1, max_length=64)
    forecast_summary: TargetWeatherSummaryPrompt
    units: TargetWeatherUnitsPrompt
    elevation_m: float | None = Field(default=None, ge=-500, le=10_000)
    caveats: list[str] = Field(max_length=10)

    _retrieved_timestamp = field_validator("retrieved_at")(_bounded_timestamp)

    @model_validator(mode="after")
    def validate_status_relationship(self) -> TargetWeatherPrompt:
        summary = self.forecast_summary.model_dump()
        has_forecast = any(
            value is not None and (not isinstance(value, list) or bool(value))
            for value in summary.values()
        )
        if self.status == "available" and (not has_forecast or self.elevation_m is None):
            raise ValueError("available weather requires forecast and elevation evidence")
        if self.status == "partial" and not (has_forecast or self.elevation_m is not None):
            raise ValueError("partial weather requires at least one evidence family")
        if self.status == "unavailable" and (has_forecast or self.elevation_m is not None):
            raise ValueError("unavailable weather cannot contain forecast or elevation evidence")
        if any(not item or len(item) > 500 for item in self.caveats):
            raise ValueError("weather caveat text is invalid")
        return self


class TargetSynthesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species_code: str = Field(min_length=1, max_length=64)
    common_name: str | None = Field(default=None, max_length=200)
    scientific_name: str | None = Field(default=None, max_length=200)
    taxonomic_category: Literal["species", "hybrid"]
    origin: TargetOriginPrompt
    window_start: str = Field(min_length=1, max_length=64)
    window_end: str = Field(min_length=1, max_length=64)
    duration_minutes: int = Field(gt=0, le=1440)
    radius_miles: float = Field(ge=1, le=300)
    evidence_freshness_at: str | None = Field(default=None, max_length=64)
    weather: TargetWeatherPrompt
    candidates: list[TargetLocationPrompt] = Field(max_length=10)
    caveats: list[str] = Field(max_length=20)

    _window_start_timestamp = field_validator("window_start")(_bounded_timestamp)
    _window_end_timestamp = field_validator("window_end")(_bounded_timestamp)

    @field_validator("evidence_freshness_at")
    @classmethod
    def validate_optional_freshness(cls, value: str | None) -> str | None:
        return _bounded_timestamp(value) if value is not None else None

    evidence_hash: str = Field(default="", pattern=r"^[0-9a-f]*$")

    def _expected_evidence_hash(self) -> str:
        evidence = {
            "species_code": self.species_code,
            "common_name": self.common_name,
            "scientific_name": self.scientific_name,
            "taxonomic_category": self.taxonomic_category,
            "origin": self.origin.model_dump(mode="json"),
            "window_start": self.window_start,
            "window_end": self.window_end,
            "duration_minutes": self.duration_minutes,
            "radius_miles": self.radius_miles,
            "evidence_freshness_at": self.evidence_freshness_at,
            "weather": self.weather.model_dump(mode="json"),
            "candidates": [item.model_dump(mode="json") for item in self.candidates],
            "caveats": self.caveats,
        }
        serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    @model_validator(mode="after")
    def validate_bounded_payload(self) -> TargetSynthesisRequest:
        self.evidence_hash = self._expected_evidence_hash()
        if any(not item or len(item) > 500 for item in self.caveats):
            raise ValueError("caveat text exceeds the allowed size")
        if len({item.location_id for item in self.candidates}) != len(self.candidates):
            raise ValueError("candidate location IDs must be unique")
        if len(self.model_dump_json().encode()) > MAX_MODEL_INPUT_BYTES:
            raise ValueError("model input exceeds the allowed serialized size")
        return self


class TargetSynthesisGrounding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species_code: str = Field(min_length=1, max_length=64)
    requested_location: str = Field(min_length=1, max_length=300)
    window_start: str = Field(min_length=1, max_length=64)
    window_end: str = Field(min_length=1, max_length=64)
    duration_minutes: int = Field(gt=0, le=1440)
    radius_miles: float = Field(ge=1, le=300)
    candidate_ids: list[str] = Field(max_length=10)
    evidence_freshness_at: str | None = Field(default=None, max_length=64)
    weather_status: Literal["available", "partial", "unavailable"]
    evidence_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    caveats: list[str] = Field(max_length=20)


class TargetSynthesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_ids: list[TargetActionId] = Field(min_length=1, max_length=5)
    grounding: TargetSynthesisGrounding

    @model_validator(mode="after")
    def validate_actions(self) -> TargetSynthesisResult:
        if len(set(self.action_ids)) != len(self.action_ids):
            raise ValueError("action_ids must be unique")
        return self


class TripPlanModelClient(Protocol):
    model: str

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult: ...


class TargetPlanModelClient(Protocol):
    model: str

    def synthesize_target(self, request: TargetSynthesisRequest) -> TargetSynthesisResult: ...


_TARGET_SYNTHESIS_JSON_SCHEMA: dict[str, Any] = TargetSynthesisResult.model_json_schema()
_TARGET_SYNTHESIS_JSON_SCHEMA["properties"]["action_ids"]["uniqueItems"] = True


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

    def synthesize_target(self, request: TargetSynthesisRequest) -> TargetSynthesisResult:
        """Return bounded target-plan actions with exact echoed grounding."""

        result = self._post_structured(
            request.model_dump_json(),
            schema_name="grounded_target_plan",
            description="Bounded target-bird actions and exact supplied grounding",
            schema=_TARGET_SYNTHESIS_JSON_SCHEMA,
            system_prompt=_TARGET_SYSTEM_PROMPT,
            result_model=TargetSynthesisResult,
        )
        validate_target_synthesis_grounding(request, result)
        return result

    def _post_structured(
        self,
        serialized_request: str,
        *,
        schema_name: str,
        description: str,
        schema: dict[str, Any],
        system_prompt: str,
        result_model: type[TargetSynthesisResult],
    ) -> TargetSynthesisResult:
        if len(serialized_request.encode()) > MAX_MODEL_INPUT_BYTES:
            raise CloudflareConfigurationError("Cloudflare model input exceeds the allowed size")
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "max_completion_tokens": MAX_MODEL_OUTPUT_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "description": description,
                    "schema": schema,
                    "strict": True,
                },
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": serialized_request},
            ],
        }
        try:
            response = self.http_post(
                _chat_completions_endpoint(self.model_base_url, self.account_id),
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
            if not isinstance(content, str) or len(content.encode()) > MAX_MODEL_OUTPUT_BYTES:
                raise ValueError("invalid model content")
            return result_model.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
            raise CloudflareMalformedResponseError(
                "Cloudflare Workers AI returned an invalid structured response"
            ) from None


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


def validate_target_synthesis_grounding(
    request: TargetSynthesisRequest, result: TargetSynthesisResult
) -> None:
    grounding = result.grounding
    expected_ids = [item.location_id for item in request.candidates]
    if grounding.species_code != request.species_code:
        raise CloudflareMalformedResponseError("Model output changed the target species")
    if grounding.requested_location != request.origin.requested_location:
        raise CloudflareMalformedResponseError("Model output changed the requested location")
    if grounding.window_start != request.window_start or grounding.window_end != request.window_end:
        raise CloudflareMalformedResponseError("Model output changed the requested time window")
    if grounding.duration_minutes != request.duration_minutes:
        raise CloudflareMalformedResponseError("Model output changed the requested duration")
    if grounding.radius_miles != request.radius_miles:
        raise CloudflareMalformedResponseError("Model output changed the travel radius")
    if grounding.candidate_ids != expected_ids:
        raise CloudflareMalformedResponseError("Model output changed the candidate locations")
    if grounding.evidence_freshness_at != request.evidence_freshness_at:
        raise CloudflareMalformedResponseError("Model output changed evidence freshness")
    if grounding.weather_status != request.weather.status:
        raise CloudflareMalformedResponseError("Model output changed weather availability")
    if grounding.evidence_hash != request.evidence_hash:
        raise CloudflareMalformedResponseError("Model output changed the supplied evidence")
    if grounding.caveats != request.caveats:
        raise CloudflareMalformedResponseError("Model output changed evidence caveats")
    if not set(result.action_ids).issubset(_ALLOWED_TARGET_ACTION_IDS):
        raise CloudflareMalformedResponseError("Model output selected an unknown target action")


_TARGET_SYSTEM_PROMPT = """Select bounded target-bird planning actions from supplied evidence.
Return only the strict JSON schema. Echo species_code, requested_location, window,
duration, radius, candidate location IDs in exact order, evidence freshness,
weather_status, evidence_hash, and caveats without changing them. The complete
candidate coordinates, names, counts, dates, distances, source freshness, normalized
weather summary/units/elevation/retrieval time, target, and request are supplied as
bounded facts. Allowed actions: try_top_location, arrive_early,
review_freshness, check_weather, verify_access. Do not add bird facts, locations,
access claims, personal history, prose, SQL, or tool calls."""


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
