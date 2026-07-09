#!/usr/bin/env python3
"""Opt-in live smoke for the allowlisted Cloudflare Workers AI model."""

from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareWorkersAIClient,
    GroundedSynthesisRequest,
)
from databox.config.settings import settings


def main() -> int:
    client = CloudflareWorkersAIClient.from_settings(settings)
    if client.model != CLOUDFLARE_WORKERS_AI_MODEL:
        raise RuntimeError("Cloudflare model allowlist violation")
    result = client.synthesize(
        GroundedSynthesisRequest(
            requested_location="34.5400,-112.4685",
            normalized_location_name="Prescott, AZ",
            window_start="2026-07-10T06:00:00",
            window_end="2026-07-10T07:00:00",
            duration_minutes=60,
            weather_summary={"status": "smoke", "hourly_rows": 0},
            recommendations=[],
            caveats=["Live smoke uses no warehouse evidence"],
            evidence_source_counts={},
        )
    )
    print(
        f"Cloudflare Workers AI smoke passed: model={client.model} "
        f"selected_actions={len(result.action_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
