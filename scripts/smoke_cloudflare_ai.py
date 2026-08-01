#!/usr/bin/env python3
"""Opt-in live smokes for every allowlisted Cloudflare structured-output contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareWorkersAIClient,
    GroundedSynthesisRequest,
    GroundedSynthesisResult,
    TargetSynthesisRequest,
    TargetSynthesisResult,
    WatchClusterPrompt,
    WatchReportSynthesisRequest,
    WatchReportSynthesisResult,
)
from databox.config.settings import settings


class SmokeClient(Protocol):
    model: str

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult: ...

    def synthesize_target(self, request: TargetSynthesisRequest) -> TargetSynthesisResult: ...

    def synthesize_watch_report(
        self, request: WatchReportSynthesisRequest
    ) -> WatchReportSynthesisResult: ...


@dataclass(frozen=True)
class SmokeResults:
    trip_actions: int
    target_actions: int
    watch_emphasis: int


def build_trip_request() -> GroundedSynthesisRequest:
    return GroundedSynthesisRequest(
        requested_location="34.5400,-112.4685",
        normalized_location_name="Prescott, AZ",
        window_start="2026-07-10T06:00:00",
        window_end="2026-07-10T07:00:00",
        duration_minutes=60,
        weather_summary={"status": "smoke", "hourly_rows": 0},
        recommendations=[],
        caveats=["Synthetic live schema smoke; no warehouse evidence."],
        evidence_source_counts={},
    )


def build_target_request() -> TargetSynthesisRequest:
    return TargetSynthesisRequest.model_validate(
        {
            "species_code": "smoke1",
            "common_name": "Synthetic Smoke Bird",
            "scientific_name": "Avis synthetica",
            "taxonomic_category": "species",
            "origin": {
                "requested_location": "Prescott",
                "normalized_location_name": "Prescott, AZ",
                "latitude": 34.54,
                "longitude": -112.4685,
                "timezone": "America/Phoenix",
                "region_code": "US-AZ",
            },
            "window_start": "2026-07-11T06:00:00",
            "window_end": "2026-07-11T08:00:00",
            "duration_minutes": 120,
            "radius_miles": 25,
            "evidence_freshness_at": "2026-07-10T14:00:00+00:00",
            "weather": {
                "status": "available",
                "retrieved_at": "2026-07-10T14:05:00+00:00",
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
                "elevation_m": 1636.0,
                "caveats": [],
            },
            "candidates": [
                {
                    "location_id": "synthetic-public-location",
                    "location_name": "Synthetic Public Smoke Location",
                    "latitude": 34.55,
                    "longitude": -112.45,
                    "observation_count": 2,
                    "latest_observation_at": "2026-07-10T14:00:00+00:00",
                    "distance_km": 2.0,
                    "distance_miles": 1.243,
                    "evidence_loaded_at": "2026-07-10T14:05:00+00:00",
                }
            ],
            "caveats": ["Synthetic live schema smoke; no warehouse evidence."],
        }
    )


def build_watch_request() -> WatchReportSynthesisRequest:
    target = build_target_request()
    return WatchReportSynthesisRequest(
        species_code=target.species_code,
        common_name=target.common_name,
        scientific_name=target.scientific_name,
        confirmed_location=WatchClusterPrompt(
            location_id="synthetic-public-location",
            location_name="Synthetic Public Smoke Location",
            latitude=34.55,
            longitude=-112.45,
            independent_submission_count=2,
            latest_observation_at="2026-07-10T14:00:00+00:00",
            distance_km=2.0,
            distance_miles=1.243,
            evidence_loaded_at="2026-07-10T14:05:00+00:00",
        ),
        morning_start="2026-07-11T11:30:00+00:00",
        morning_end="2026-07-11T13:30:00+00:00",
        event_horizon_end="2026-07-15T13:30:00+00:00",
        evidence_freshness_at="2026-07-10T14:00:00+00:00",
        weather=target.weather,
        caveats=["Synthetic live schema smoke; no warehouse evidence."],
    )


def run_live_smokes(client: SmokeClient) -> SmokeResults:
    trip = client.synthesize(build_trip_request())
    target = client.synthesize_target(build_target_request())
    watch = client.synthesize_watch_report(build_watch_request())
    return SmokeResults(
        trip_actions=len(trip.action_ids),
        target_actions=len(target.action_ids),
        watch_emphasis=len(watch.emphasis_ids),
    )


def success_message(model: str, result: SmokeResults) -> str:
    return (
        f"Cloudflare Workers AI smokes passed: model={model} schemas=trip,target,watch "
        f"trip_actions={result.trip_actions} target_actions={result.target_actions} "
        f"watch_emphasis={result.watch_emphasis}"
    )


def main() -> int:
    client = CloudflareWorkersAIClient.from_settings(settings)
    if client.model != CLOUDFLARE_WORKERS_AI_MODEL:
        raise RuntimeError("Cloudflare model allowlist violation")
    results = run_live_smokes(client)
    print(success_message(client.model, results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
