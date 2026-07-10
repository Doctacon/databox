from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb
import pytest
from databox.agent_tools import recommendation_media_backfill as backfill
from databox.agent_tools.persistence import ensure_birding_agent_persistence_tables
from databox.agent_tools.recommendation_media import GBIF_OCCURRENCE_SEARCH, XENO_CANTO_RECORDINGS
from databox.agent_tools.recommendation_media_backfill import run_media_backfill
from databox.api import create_app
from fastapi.testclient import TestClient


def _database(path: Path) -> None:
    with duckdb.connect(str(path)) as connection:
        ensure_birding_agent_persistence_tables(connection)
        plans = (("plan-queen", "Queen Valley, Arizona"), ("plan-other", "Prescott"))
        for plan_id, location in plans:
            connection.execute(
                """
                INSERT INTO birding_agent.trip_plans (
                    trip_plan_id, requested_location, window_start, window_end,
                    duration_minutes, plan_status, field_plan_text, created_at, updated_at
                ) VALUES (?, ?, '2026-07-10T06:00:00', '2026-07-10T07:30:00',
                          90, 'complete', ?, '2026-07-09T12:00:00', '2026-07-09T12:00:00')
                """,
                [plan_id, location, f"Field plan for {location}"],
            )
        for recommendation_id, plan_id, rank, common_name, scientific_name in (
            ("rec-queen", "plan-queen", 1, "Mexican Jay", "Aphelocoma wollweberi"),
            ("rec-other", "plan-other", 1, "Zone-tailed Hawk", "Buteo albonotatus"),
        ):
            connection.execute(
                """
                INSERT INTO birding_agent.trip_plan_recommendations (
                    recommendation_id, trip_plan_id, common_name, scientific_name,
                    recommendation_group, rank_order, confidence_label, rationale_text,
                    created_at
                ) VALUES (?, ?, ?, ?, 'high_likelihood', ?, 'high', ?, '2026-07-09T12:00:00')
                """,
                [
                    recommendation_id,
                    plan_id,
                    common_name,
                    scientific_name,
                    rank,
                    f"Why {common_name}",
                ],
            )


def _immutable_hash(connection: duckdb.DuckDBPyConnection) -> str:
    plans = connection.execute(
        "SELECT * FROM birding_agent.trip_plans ORDER BY trip_plan_id"
    ).fetchall()
    recommendations = connection.execute(
        "SELECT * FROM birding_agent.trip_plan_recommendations ORDER BY recommendation_id"
    ).fetchall()
    return hashlib.sha256(repr((plans, recommendations)).encode()).hexdigest()


def _gbif_getter(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    assert endpoint == GBIF_OCCURRENCE_SEARCH
    species = str(params["scientificName"])
    if species == "Buteo albonotatus":
        raise TimeoutError
    identifier = "https://example.org/mexican-jay.jpg"
    return {
        "results": [
            {
                "key": 101,
                "species": species,
                "countryCode": "US",
                "stateProvince": "Arizona",
                "institutionCode": "fixture",
                "media": [
                    {
                        "type": "StillImage",
                        "format": "image/jpeg",
                        "identifier": identifier,
                        "creator": "Fixture Creator",
                        "rightsHolder": "Fixture Rights",
                        "license": "https://creativecommons.org/licenses/by/4.0/",
                    }
                ],
            }
        ]
    }


def _xeno_getter(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    assert endpoint == XENO_CANTO_RECORDINGS
    query = str(params["query"])
    if 'gen:"Buteo"' in query:
        raise TimeoutError
    return {
        "recordings": [
            {
                "id": "202",
                "gen": "Aphelocoma",
                "sp": "wollweberi",
                "rec": "Fixture Recordist",
                "cnt": "United States",
                "loc": "Pinal County, Arizona",
                "url": "https://xeno-canto.org/202",
                "file": "https://xeno-canto.org/202/download",
                "lic": "https://creativecommons.org/licenses/by/4.0/",
                "type": "call",
                "q": "A",
            }
        ]
    }


def _seed_complete_media(
    path: Path,
    *,
    candidate_id: str,
    candidate_status: str,
    candidate_caveats: str,
) -> None:
    with duckdb.connect(str(path)) as connection:
        for recommendation_id in ("rec-queen", "rec-other"):
            for evidence_type, source in (
                ("recommendation_photo", "gbif"),
                ("recommendation_call", "xeno_canto"),
            ):
                is_candidate = (
                    recommendation_id == "rec-queen" and evidence_type == "recommendation_photo"
                )
                connection.execute(
                    """
                    INSERT INTO birding_agent.trip_plan_evidence (
                        evidence_id, trip_plan_id, recommendation_id, source,
                        evidence_type, status, summary_json, payload_json, caveats_json
                    ) VALUES (?, ?, ?, ?, ?, ?, '{}', '{}', ?)
                    """,
                    [
                        candidate_id
                        if is_candidate
                        else f"existing_{recommendation_id}_{evidence_type}",
                        "plan-queen" if recommendation_id == "rec-queen" else "plan-other",
                        recommendation_id,
                        source,
                        evidence_type,
                        candidate_status if is_candidate else "available",
                        candidate_caveats if is_candidate else "[]",
                    ],
                )


def _evidence_rows(path: Path) -> list[tuple[Any, ...]]:
    with duckdb.connect(str(path), read_only=True) as connection:
        return connection.execute(
            "SELECT * FROM birding_agent.trip_plan_evidence ORDER BY evidence_id"
        ).fetchall()


def test_dry_run_reports_targets_without_discovery_or_writes(tmp_path: Path) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    calls = 0

    def forbidden_getter(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError((endpoint, params))

    with duckdb.connect(str(path), read_only=True) as connection:
        before = _immutable_hash(connection)
    result = run_media_backfill(
        str(path), apply=False, gbif_getter=forbidden_getter, xeno_getter=forbidden_getter
    )
    with duckdb.connect(str(path), read_only=True) as connection:
        assert _immutable_hash(connection) == before
        assert (
            connection.execute("SELECT count(*) FROM birding_agent.trip_plan_evidence").fetchone()[
                0
            ]
            == 0
        )
    assert calls == 0
    assert result.plan_count == 2
    assert result.recommendation_count == 2
    assert result.target_recommendation_count == 2
    assert result.missing_photo_count == result.missing_call_count == 2
    assert result.lookup_count == 0


def test_apply_is_partial_failure_safe_idempotent_and_model_free(
    tmp_path: Path, monkeypatch: Any
) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)

    def forbidden_model(*args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr(
        "databox.agents.cloudflare_workers_ai.CloudflareWorkersAIClient.synthesize",
        forbidden_model,
    )
    with duckdb.connect(str(path), read_only=True) as connection:
        before = _immutable_hash(connection)

    first = run_media_backfill(
        str(path),
        apply=True,
        gbif_getter=_gbif_getter,
        xeno_getter=_xeno_getter,
        xeno_api_key="test-key",
    )
    with duckdb.connect(str(path), read_only=True) as connection:
        assert _immutable_hash(connection) == before
        rows = connection.execute(
            """
            SELECT recommendation_id, evidence_type, status, count(*)
            FROM birding_agent.trip_plan_evidence
            GROUP BY ALL ORDER BY 1, 2
            """
        ).fetchall()
    assert rows == [
        ("rec-other", "recommendation_call", "unavailable", 1),
        ("rec-other", "recommendation_photo", "unavailable", 1),
        ("rec-queen", "recommendation_call", "available", 1),
        ("rec-queen", "recommendation_photo", "available", 1),
    ]
    assert first.inserted_photo_count == first.inserted_call_count == 2
    assert first.inserted_available_count == first.inserted_unavailable_count == 2

    second = run_media_backfill(
        str(path),
        apply=True,
        gbif_getter=lambda *_: (_ for _ in ()).throw(AssertionError("unexpected GBIF")),
        xeno_getter=lambda *_: (_ for _ in ()).throw(AssertionError("unexpected Xeno")),
        xeno_api_key="test-key",
    )
    assert second.target_recommendation_count == 0
    assert second.inserted_photo_count == second.inserted_call_count == 0
    assert second.lookup_count == 0


def test_apply_fills_only_missing_type_and_get_remains_read_only(tmp_path: Path) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """
            INSERT INTO birding_agent.trip_plan_evidence (
                evidence_id, trip_plan_id, recommendation_id, source, evidence_type,
                status, summary_json, payload_json, caveats_json
            ) VALUES ('media_backfill_v2_legacy', 'plan-queen', 'rec-queen', 'gbif',
                      'recommendation_photo', 'unavailable',
                      '{"kind":"photo","status":"unavailable"}', '{}',
                      '["No eligible exact-species Arizona GBIF photo was found"]')
            """
        )
    result = run_media_backfill(
        str(path),
        apply=True,
        gbif_getter=_gbif_getter,
        xeno_getter=_xeno_getter,
        xeno_api_key="test-key",
    )
    assert result.missing_photo_count == 1
    assert result.missing_call_count == 2
    assert result.replaced_photo_count == 1
    with duckdb.connect(str(path), read_only=True) as connection:
        before = connection.execute(
            "SELECT count(*), md5(string_agg(evidence_id, ',' ORDER BY evidence_id)) "
            "FROM birding_agent.trip_plan_evidence"
        ).fetchone()
        assert (
            connection.execute(
                """
            SELECT count(*) FROM (
                SELECT recommendation_id, evidence_type
                FROM birding_agent.trip_plan_evidence
                WHERE evidence_type IN ('recommendation_photo', 'recommendation_call')
                GROUP BY ALL HAVING count(*) != 1
            )
            """
            ).fetchone()[0]
            == 0
        )

    app = create_app(
        database_path=str(path),
        media_gbif_getter=lambda *_: (_ for _ in ()).throw(AssertionError("GET called GBIF")),
        media_xeno_getter=lambda *_: (_ for _ in ()).throw(AssertionError("GET called Xeno")),
    )
    response = TestClient(app).get("/api/trip-plans/plan-queen")
    assert response.status_code == 200
    assert response.json()["recommendations"][0]["photo"]["status"] == "available"
    assert response.json()["recommendations"][0]["call"]["status"] == "available"
    with duckdb.connect(str(path), read_only=True) as connection:
        after = connection.execute(
            "SELECT count(*), md5(string_agg(evidence_id, ',' ORDER BY evidence_id)) "
            "FROM birding_agent.trip_plan_evidence"
        ).fetchone()
    assert after == before


@pytest.mark.parametrize(
    ("evidence_id", "status", "caveats"),
    [
        (
            "media_backfill_legacy",
            "unavailable",
            '["No eligible exact-species Arizona GBIF photo was found"]',
        ),
        (
            "media_backfill_v1_unknown",
            "unavailable",
            '["No eligible exact-species Arizona GBIF photo was found"]',
        ),
        (
            "media_backfill_unknown_version",
            "unavailable",
            '["No eligible exact-species Arizona GBIF photo was found"]',
        ),
        (
            "media_backfill_v3_current",
            "unavailable",
            '["No eligible exact-species Arizona GBIF photo was found"]',
        ),
        ("media_backfill_v2_changed_caveat", "unavailable", '["Different caveat"]'),
        (
            "media_backfill_v2_available",
            "available",
            '["No eligible exact-species Arizona GBIF photo was found"]',
        ),
    ],
)
def test_only_exact_defective_v2_unavailable_photo_is_retried(
    tmp_path: Path, evidence_id: str, status: str, caveats: str
) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    _seed_complete_media(
        path,
        candidate_id=evidence_id,
        candidate_status=status,
        candidate_caveats=caveats,
    )
    result = run_media_backfill(str(path), apply=False)
    assert result.target_recommendation_count == 0
    assert result.replaced_photo_count == 0


def test_exact_defective_v2_unavailable_photo_is_one_time_target(tmp_path: Path) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    _seed_complete_media(
        path,
        candidate_id="media_backfill_v2_defective",
        candidate_status="unavailable",
        candidate_caveats='["No eligible exact-species Arizona GBIF photo was found"]',
    )
    result = run_media_backfill(str(path), apply=False)
    assert result.target_recommendation_count == 1


def test_selector_failure_rolls_back_without_evidence(tmp_path: Path, monkeypatch: Any) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)

    def fail_selector(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected selector failure")

    monkeypatch.setattr(backfill, "enrich_recommendation_media", fail_selector)
    with pytest.raises(RuntimeError, match="injected selector failure"):
        run_media_backfill(str(path), apply=True, xeno_api_key="test-key")
    assert _evidence_rows(path) == []


def test_mid_persistence_failure_rolls_back_all_inserts(tmp_path: Path, monkeypatch: Any) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    original_insert = backfill._insert_media_evidence
    insertion_count = 0

    def fail_after_first_insert(*args: Any, **kwargs: Any) -> None:
        nonlocal insertion_count
        insertion_count += 1
        if insertion_count == 2:
            raise RuntimeError("injected persistence failure")
        original_insert(*args, **kwargs)

    monkeypatch.setattr(backfill, "_insert_media_evidence", fail_after_first_insert)
    with pytest.raises(RuntimeError, match="injected persistence failure"):
        run_media_backfill(
            str(path),
            apply=True,
            gbif_getter=_gbif_getter,
            xeno_getter=_xeno_getter,
            xeno_api_key="test-key",
        )
    assert insertion_count == 2
    assert _evidence_rows(path) == []


def test_duplicate_media_aborts_before_discovery_or_writes(tmp_path: Path) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    with duckdb.connect(str(path)) as connection:
        for evidence_id in ("duplicate-a", "duplicate-b"):
            connection.execute(
                """
                INSERT INTO birding_agent.trip_plan_evidence (
                    evidence_id, trip_plan_id, recommendation_id, source,
                    evidence_type, status, summary_json, payload_json
                ) VALUES (?, 'plan-queen', 'rec-queen', 'gbif',
                          'recommendation_photo', 'unavailable', '{}', '{}')
                """,
                [evidence_id],
            )
    before = _evidence_rows(path)
    discoveries = 0

    def forbidden_getter(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        nonlocal discoveries
        discoveries += 1
        raise AssertionError((endpoint, params))

    with pytest.raises(RuntimeError, match="Duplicate recommendation media evidence"):
        run_media_backfill(
            str(path),
            apply=True,
            gbif_getter=forbidden_getter,
            xeno_getter=forbidden_getter,
            xeno_api_key="test-key",
        )
    assert discoveries == 0
    assert _evidence_rows(path) == before


def test_external_duckdb_lock_fails_before_mutation(tmp_path: Path) -> None:
    path = tmp_path / "databox.duckdb"
    ready = tmp_path / "locked"
    _database(path)
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import time; from pathlib import Path; import duckdb; "
                f"con=duckdb.connect({str(path)!r}); Path({str(ready)!r}).write_text('ready'); "
                "time.sleep(30)"
            ),
        ]
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists()
        with pytest.raises(duckdb.IOException, match="Could not set lock"):
            run_media_backfill(str(path), apply=True, xeno_api_key="test-key")
    finally:
        holder.terminate()
        holder.wait(timeout=10)
    assert _evidence_rows(path) == []
