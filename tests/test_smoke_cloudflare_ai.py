"""Offline contract tests for the opt-in Cloudflare live smoke harness."""

from __future__ import annotations

import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from databox.agents.cloudflare_workers_ai import CLOUDFLARE_WORKERS_AI_MODEL

SCRIPT = Path(__file__).parents[1] / "scripts" / "smoke_cloudflare_ai.py"
MODULE = runpy.run_path(str(SCRIPT))
build_target_request = cast(Any, MODULE["build_target_request"])
build_watch_request = cast(Any, MODULE["build_watch_request"])
run_live_smokes = cast(Any, MODULE["run_live_smokes"])
success_message = cast(Any, MODULE["success_message"])


class FakeSmokeClient:
    model = CLOUDFLARE_WORKERS_AI_MODEL

    def __init__(self) -> None:
        self.contracts: list[str] = []

    def synthesize(self, request: object) -> SimpleNamespace:
        self.contracts.append("trip")
        return SimpleNamespace(action_ids=["listen_first"])

    def synthesize_target(self, request: object) -> SimpleNamespace:
        self.contracts.append("target")
        return SimpleNamespace(action_ids=["try_top_location", "verify_access"])

    def synthesize_watch_report(self, request: object) -> SimpleNamespace:
        self.contracts.append("watch")
        return SimpleNamespace(emphasis_ids=["freshness", "uncertainty"])


def test_live_smoke_harness_exercises_all_distinct_contracts() -> None:
    client = FakeSmokeClient()

    results = run_live_smokes(client)

    assert client.contracts == ["trip", "target", "watch"]
    assert (results.trip_actions, results.target_actions, results.watch_emphasis) == (1, 2, 2)
    assert success_message(client.model, results) == (
        "Cloudflare Workers AI smokes passed: "
        "model=@cf/zai-org/glm-4.7-flash schemas=trip,target,watch "
        "trip_actions=1 target_actions=2 watch_emphasis=2"
    )


def test_live_smoke_fixtures_are_synthetic_bounded_and_hash_grounded() -> None:
    target = build_target_request()
    watch = build_watch_request()

    assert target.species_code == "smoke1"
    assert [item.location_id for item in target.candidates] == ["synthetic-public-location"]
    assert len(target.evidence_hash) == 64
    assert watch.species_code == target.species_code
    assert watch.confirmed_location.location_id == "synthetic-public-location"
    assert len(watch.fact_hash) == 64
    assert "watch_center" not in watch.model_dump()
