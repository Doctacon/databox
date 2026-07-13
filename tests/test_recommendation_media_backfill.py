from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb
import pytest
from databox.agent_tools import recommendation_media_backfill as backfill
from databox.agent_tools.persistence import ensure_birding_agent_persistence_tables
from databox.agent_tools.recommendation_media import (
    XENO_CANTO_RECORDINGS,
    RecommendationMediaBatch,
    RecommendationMediaEvidence,
)
from databox.agent_tools.recommendation_media_backfill import run_media_backfill
from databox.api import create_app
from databox.curated_photo import CuratedPhotoResult
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _deterministic_curated_selector(monkeypatch: Any) -> None:
    def select(scientific_name: str, **_kwargs: Any) -> CuratedPhotoResult:
        return CuratedPhotoResult(
            status="available",
            source="inaturalist",
            source_record_id="42",
            species_name=scientific_name,
            display_url="https://inaturalist-open-data.s3.amazonaws.com/photos/42/large.jpg",
            source_url="https://www.inaturalist.org/photos/42",
            creator="Fixture Creator",
            license_code="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            original_width=1600,
            original_height=1200,
            selection_reason="Deterministic curated fixture",
            lookup_at="2026-07-12T00:00:00+00:00",
            identity={"taxon_id": 7, "photo_id": 42, "curated_position": 1},
            attempted_sources=("inaturalist",),
        )

    monkeypatch.setattr("databox.curated_photo.select_curated_photo", select)


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
    result = run_media_backfill(str(path), apply=False, xeno_getter=forbidden_getter)
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
        ("rec-other", "recommendation_photo", "available", 1),
        ("rec-queen", "recommendation_call", "available", 1),
        ("rec-queen", "recommendation_photo", "available", 1),
    ]
    assert first.inserted_photo_count == first.inserted_call_count == 2
    assert first.inserted_available_count == 3
    assert first.inserted_unavailable_count == 1

    second = run_media_backfill(
        str(path),
        apply=True,
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


def _curated_batch(recommendations: list[Any]) -> RecommendationMediaBatch:
    evidence = []
    for item in recommendations:
        photo_id = "101" if item.recommendation_id == "rec-queen" else "202"
        evidence.append(
            RecommendationMediaEvidence(
                recommendation_id=item.recommendation_id,
                source="inaturalist",
                source_record_id=photo_id,
                evidence_type="recommendation_photo",
                status="available",
                summary={
                    "kind": "photo",
                    "status": "available",
                    "provider": "inaturalist",
                    "species_name": item.scientific_name,
                    "display_url": (
                        "https://inaturalist-open-data.s3.amazonaws.com/"
                        f"photos/{photo_id}/large.jpg"
                    ),
                    "source_url": f"https://www.inaturalist.org/photos/{photo_id}",
                    "creator": "Fixture Creator",
                    "license_text": "CC BY 4.0",
                    "license_code": "CC BY 4.0",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                    "original_width": 1600,
                    "original_height": 1200,
                    "selection_reason": "Deterministic curated fixture",
                },
                payload={
                    "identity": {
                        "taxon_id": 7,
                        "photo_id": int(photo_id),
                        "curated_position": 1,
                    },
                    "attempted_sources": ["inaturalist"],
                },
            )
        )
    return RecommendationMediaBatch(
        evidence=evidence,
        lookup_count=len(evidence) * 2,
        available_photos=len(evidence),
        available_calls=0,
        arizona_calls=0,
        global_calls=0,
    )


def test_curated_photo_only_replaces_legacy_photos_preserves_calls_and_is_idempotent(
    tmp_path: Path, monkeypatch: Any
) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    _seed_complete_media(
        path,
        candidate_id="existing_rec-queen_recommendation_photo",
        candidate_status="available",
        candidate_caveats="[]",
    )
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """
            INSERT INTO birding_agent.trip_plan_evidence (
                evidence_id, trip_plan_id, recommendation_id, source, evidence_type,
                status, summary_json, payload_json, caveats_json
            ) VALUES ('gbif-context', 'plan-queen', 'rec-queen', 'gbif',
                      'occurrence_context', 'available', '{}', '{}', '[]')
            """
        )
        immutable_before = _immutable_hash(connection)
        calls_before = connection.execute(
            """
            SELECT * FROM birding_agent.trip_plan_evidence
            WHERE evidence_type = 'recommendation_call' ORDER BY evidence_id
            """
        ).fetchall()
        context_before = connection.execute(
            "SELECT * FROM birding_agent.trip_plan_evidence WHERE evidence_id = 'gbif-context'"
        ).fetchall()

    monkeypatch.setattr(
        backfill, "enrich_recommendation_media", lambda items, **_: _curated_batch(items)
    )
    first = run_media_backfill(str(path), apply=True, curated_photos_only=True)
    assert first.target_recommendation_count == 2
    assert first.replaced_photo_count == 2
    assert first.inserted_photo_count == 2
    assert first.inserted_call_count == 0
    with duckdb.connect(str(path), read_only=True) as connection:
        assert _immutable_hash(connection) == immutable_before
        assert (
            connection.execute(
                """
                SELECT * FROM birding_agent.trip_plan_evidence
                WHERE evidence_type = 'recommendation_call' ORDER BY evidence_id
                """
            ).fetchall()
            == calls_before
        )
        assert (
            connection.execute(
                "SELECT * FROM birding_agent.trip_plan_evidence WHERE evidence_id = 'gbif-context'"
            ).fetchall()
            == context_before
        )
        assert connection.execute(
            """
            SELECT source, count(*) FROM birding_agent.trip_plan_evidence
            WHERE evidence_type = 'recommendation_photo' GROUP BY source
            """
        ).fetchall() == [("inaturalist", 2)]

    monkeypatch.setattr(
        backfill,
        "enrich_recommendation_media",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected lookup")),
    )
    second = run_media_backfill(str(path), apply=True, curated_photos_only=True)
    assert second.target_recommendation_count == 0
    assert second.lookup_count == 0
    assert second.inserted_photo_count == 0


def test_curated_photo_only_commits_each_completed_recommendation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    _seed_complete_media(
        path,
        candidate_id="existing_rec-queen_recommendation_photo",
        candidate_status="available",
        candidate_caveats="[]",
    )
    monkeypatch.setattr(
        backfill, "enrich_recommendation_media", lambda items, **_: _curated_batch(items)
    )
    original_insert = backfill._insert_media_evidence
    inserts = 0

    def fail_second(*args: Any, **kwargs: Any) -> None:
        nonlocal inserts
        inserts += 1
        if inserts == 2:
            raise RuntimeError("injected persistence failure")
        original_insert(*args, **kwargs)

    monkeypatch.setattr(backfill, "_insert_media_evidence", fail_second)
    with pytest.raises(RuntimeError, match="injected persistence failure"):
        run_media_backfill(str(path), apply=True, curated_photos_only=True)
    with duckdb.connect(str(path), read_only=True) as connection:
        assert (
            connection.execute(
                """
                SELECT count(*) FROM birding_agent.trip_plan_evidence
                WHERE evidence_type = 'recommendation_photo' AND source = 'inaturalist'
                """
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                """
                SELECT count(*) FROM birding_agent.trip_plan_evidence
                WHERE evidence_type = 'recommendation_photo' AND source = 'gbif'
                """
            ).fetchone()[0]
            == 1
        )


def test_curated_lookup_interruption_resumes_without_repeating_checkpoint(
    tmp_path: Path, monkeypatch: Any
) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    _seed_complete_media(
        path,
        candidate_id="existing_rec-queen_recommendation_photo",
        candidate_status="available",
        candidate_caveats="[]",
    )
    looked_up: list[str] = []

    def interrupt_second(items: list[Any], **_: Any) -> RecommendationMediaBatch:
        looked_up.append(items[0].recommendation_id)
        if len(looked_up) == 2:
            raise RuntimeError("injected lookup failure")
        return _curated_batch(items)

    monkeypatch.setattr(backfill, "enrich_recommendation_media", interrupt_second)
    with pytest.raises(RuntimeError, match="injected lookup failure"):
        run_media_backfill(str(path), apply=True, curated_photos_only=True)
    assert looked_up == ["rec-other", "rec-queen"]

    resumed: list[str] = []

    def resume(items: list[Any], **_: Any) -> RecommendationMediaBatch:
        resumed.append(items[0].recommendation_id)
        return _curated_batch(items)

    monkeypatch.setattr(backfill, "enrich_recommendation_media", resume)
    result = run_media_backfill(str(path), apply=True, curated_photos_only=True)
    assert resumed == ["rec-queen"]
    assert result.target_recommendation_count == 1
    with duckdb.connect(str(path), read_only=True) as connection:
        assert (
            connection.execute(
                """SELECT count(*) FROM birding_agent.trip_plan_evidence
            WHERE evidence_type='recommendation_photo' AND source='inaturalist'"""
            ).fetchone()[0]
            == 2
        )


def test_malformed_curated_singleton_is_not_treated_as_complete(
    tmp_path: Path, monkeypatch: Any
) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    monkeypatch.setattr(
        backfill, "enrich_recommendation_media", lambda items, **_: _curated_batch(items)
    )
    run_media_backfill(str(path), apply=True, curated_photos_only=True)
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """UPDATE birding_agent.trip_plan_evidence
            SET summary_json=json_merge_patch(summary_json, '{"species_name":"Wrong species"}')
            WHERE recommendation_id='rec-queen' AND evidence_type='recommendation_photo'"""
        )
    dry_run = run_media_backfill(str(path), apply=False, curated_photos_only=True)
    assert dry_run.target_recommendation_count == 1
    repaired = run_media_backfill(str(path), apply=True, curated_photos_only=True)
    assert repaired.replaced_photo_count == 1


def test_selector_failure_rolls_back_without_evidence(tmp_path: Path, monkeypatch: Any) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)

    def fail_selector(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected selector failure")

    monkeypatch.setattr(backfill, "enrich_recommendation_media", fail_selector)
    with pytest.raises(RuntimeError, match="injected selector failure"):
        run_media_backfill(str(path), apply=True, xeno_api_key="test-key")
    assert _evidence_rows(path) == []


def test_mid_persistence_failure_preserves_completed_photo_checkpoint(
    tmp_path: Path, monkeypatch: Any
) -> None:
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
            xeno_getter=_xeno_getter,
            xeno_api_key="test-key",
        )
    assert insertion_count == 2
    rows = _evidence_rows(path)
    assert len(rows) == 1
    assert rows[0][2:4] == ("rec-other", "inaturalist")


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


def test_curated_photo_retry_has_durable_run_observability_and_no_op(
    tmp_path: Path, monkeypatch: Any
) -> None:
    path = tmp_path / "databox.duckdb"
    _database(path)
    attempts: Counter[str] = Counter()

    def selected(scientific_name: str, **_kwargs: Any) -> CuratedPhotoResult:
        attempts[scientific_name] += 1
        if scientific_name == "Aphelocoma wollweberi" and attempts[scientific_name] == 1:
            return CuratedPhotoResult(
                status="unavailable",
                source="curated_photo",
                source_record_id=None,
                species_name=scientific_name,
                display_url=None,
                source_url=None,
                creator=None,
                license_code=None,
                license_url=None,
                original_width=None,
                original_height=None,
                selection_reason=None,
                lookup_at="2026-07-13T00:00:00+00:00",
                identity={},
                caveats=("Retryable iNaturalist transport failure",),
                attempted_sources=("inaturalist",),
                request_count=1,
                failure_class="transport",
                retryable=True,
            )
        return CuratedPhotoResult(
            status="available",
            source="inaturalist",
            source_record_id="42",
            species_name=scientific_name,
            display_url="https://inaturalist-open-data.s3.amazonaws.com/photos/42/large.jpg",
            source_url="https://www.inaturalist.org/photos/42",
            creator="Fixture Creator",
            license_code="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            original_width=1600,
            original_height=1200,
            selection_reason="Curated fixture",
            lookup_at="2026-07-13T00:00:00+00:00",
            identity={"taxon_id": 7, "photo_id": 42, "curated_position": 1},
            attempted_sources=("inaturalist",),
            request_count=2,
        )

    monkeypatch.setattr("databox.curated_photo.select_curated_photo", selected)
    first = run_media_backfill(str(path), apply=True, curated_photos_only=True)
    assert first.remaining_missing_photo_count == 1
    assert first.request_count == 3
    assert first.run_id is not None
    connection = duckdb.connect(str(path), read_only=True)
    failed = connection.execute(
        """SELECT status, target_count, processed_count, lookup_count, request_count,
        outcomes_json, safe_failure, duration_ms
        FROM birding_agent.recommendation_photo_runs"""
    ).fetchone()
    connection.close()
    assert failed is not None
    assert failed[:5] == ("failed", 2, 1, 2, 3)
    assert json.loads(failed[5]) == {
        "inaturalist.available": 1,
        "inaturalist.failed.transport": 1,
    }
    assert failed[6] == "retryable_results_remaining"
    assert isinstance(failed[7], int)

    second = run_media_backfill(str(path), apply=True, curated_photos_only=True)
    assert second.run_id == first.run_id
    assert second.target_recommendation_count == 1
    assert second.remaining_missing_photo_count == 0
    assert second.request_count == 5
    attempts_before = attempts.copy()
    third = run_media_backfill(str(path), apply=True, curated_photos_only=True)
    assert third.target_recommendation_count == 0
    assert third.request_count == 0
    assert attempts == attempts_before
    connection = duckdb.connect(str(path), read_only=True)
    complete = connection.execute(
        """SELECT status, processed_count, lookup_count, request_count, safe_failure
        FROM birding_agent.recommendation_photo_runs"""
    ).fetchone()
    connection.close()
    assert complete == ("complete", 2, 3, 5, None)
