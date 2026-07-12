"""Local personal collection storage and API contract tests."""

from __future__ import annotations

import asyncio
import hashlib
import socket
from datetime import date, datetime
from pathlib import Path

import databox.personal_collection as collection_storage
import databox.personal_collection_api as collection_api
import duckdb
import pytest
from databox.api import create_app
from fastapi.testclient import TestClient


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "personal.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA birding_agent")
    connection.execute(
        """
        CREATE TABLE birding_agent.arizona_species_catalog (
            species_code VARCHAR,
            common_name VARCHAR,
            scientific_name VARCHAR,
            taxonomic_category VARCHAR
        )
        """
    )
    connection.execute(
        """
        INSERT INTO birding_agent.arizona_species_catalog VALUES
        ('gambqu', 'Gambel''s Quail', 'Callipepla gambelii', 'species'),
        ('sxrgoo1', 'Snow x Ross''s Goose', 'Anser caerulescens x rossii', 'hybrid')
        """
    )
    connection.close()
    return path


def _client(path: Path) -> TestClient:
    return TestClient(create_app(database_path=str(path), static_dir=path.parent / "missing"))


def _observation(species_code: str = "gambqu", day: str = "2026-07-09") -> dict[str, object]:
    return {
        "species_code": species_code,
        "observation_date": day,
        "location": "  Home garden  ",
        "notes": "  First record  ",
    }


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _watch(radius: float = 25) -> dict[str, object]:
    return {
        "center": {
            "display_name": "Phoenix, Arizona",
            "latitude": 33.4484,
            "longitude": -112.074,
            "timezone": "America/Phoenix",
            "region_code": "US-AZ",
        },
        "radius_miles": radius,
    }


def test_empty_reads_are_network_free_and_do_not_create_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    def forbidden(*_: object, **__: object) -> object:
        raise AssertionError("collection reads must not use the network")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    client = _client(path)
    assert client.get("/api/observations").json() == {"observations": []}
    assert client.get("/api/life-list").json() == {"birds": []}
    assert client.get("/api/watches").json() == {"watches": []}
    assert client.get("/api/wishlist").status_code == 404
    assert client.put("/api/wishlist/gambqu").status_code == 404
    assert client.delete("/api/wishlist/gambqu").status_code == 404
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_observations_derive_life_list_and_hard_delete_last_event(tmp_path: Path) -> None:
    path = _database(tmp_path)
    client = _client(path)

    first = client.post("/api/observations", json=_observation(day="2026-07-09"))
    second = client.post("/api/observations", json=_observation(day="2026-07-01"))
    assert first.status_code == second.status_code == 201
    first_row = first.json()
    assert first_row["location"] == "Home garden"
    assert first_row["notes"] == "First record"
    assert first_row["identity"]["catalog_status"] == "current"

    life = client.get("/api/life-list").json()["birds"]
    assert life == [
        {
            "species_code": "gambqu",
            "first_observed_date": "2026-07-01",
            "latest_observed_date": "2026-07-09",
            "observation_count": 2,
            "identity": {
                "catalog_status": "current",
                "common_name": "Gambel's Quail",
                "scientific_name": "Callipepla gambelii",
                "taxonomic_category": "species",
            },
        }
    ]

    original_id = first_row["observation_id"]
    original_created = first_row["created_at"]
    edited = client.put(
        f"/api/observations/{original_id}",
        json=_observation(species_code="sxrgoo1", day="2026-07-10"),
    )
    assert edited.status_code == 200
    assert edited.json()["observation_id"] == original_id
    assert edited.json()["created_at"] == original_created
    assert edited.json()["identity"]["taxonomic_category"] == "hybrid"

    assert client.delete(f"/api/observations/{original_id}").status_code == 409
    assert client.delete(f"/api/observations/{original_id}?confirm=true").json() == {
        "removed": True
    }
    second_id = second.json()["observation_id"]
    assert client.delete(f"/api/observations/{second_id}?confirm=true").status_code == 200
    assert client.get("/api/life-list").json() == {"birds": []}
    assert client.get(f"/api/observations/{original_id}").status_code == 404


def test_watch_and_observed_state_are_independent_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)

    def forbidden(*_: object, **__: object) -> object:
        raise AssertionError("collection mutations must not call external services")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    client = _client(path)

    assert client.post("/api/observations", json=_observation()).status_code == 201

    watch = client.put("/api/watches/gambqu", json=_watch())
    assert watch.status_code == 200
    assert watch.json()["active"] is True
    activation = watch.json()["activated_at"]
    paused = client.post("/api/watches/gambqu/pause").json()
    assert paused["active"] is False
    assert paused["activated_at"] == activation
    assert client.post("/api/watches/gambqu/pause").json()["activated_at"] == activation
    resumed = client.post("/api/watches/gambqu/resume").json()
    assert resumed["active"] is True
    assert resumed["activated_at"] >= activation

    state = client.get("/api/birds/gambqu/collection-state").json()
    assert state == {
        "species_code": "gambqu",
        "catalog_status": "current",
        "observed": True,
        "observation_count": 1,
        "watched": True,
        "watch_active": True,
    }

    assert client.delete("/api/watches/gambqu").json() == {"removed": True}
    assert client.delete("/api/watches/gambqu").json() == {"removed": True}
    state = client.get("/api/birds/gambqu/collection-state").json()
    assert state["observed"] is True
    assert state["watched"] is False


def test_validation_catalog_and_arizona_boundaries_are_safe(tmp_path: Path) -> None:
    client = _client(_database(tmp_path))

    assert client.post("/api/observations", json=_observation("missing")).status_code == 404
    assert (
        client.post("/api/observations", json={**_observation(), "extra": "secret"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/observations", json={**_observation(), "observation_date": "bad"}
        ).status_code
        == 422
    )
    assert client.put("/api/watches/gambqu", json=_watch(0.9)).status_code == 422
    assert client.put("/api/watches/gambqu", json=_watch(301)).status_code == 422
    outside = _watch()
    outside["center"] = {
        "display_name": "Albuquerque, New Mexico",
        "latitude": 35.0844,
        "longitude": -106.6504,
        "timezone": "America/Denver",
        "region_code": "US-AZ",
    }
    response = client.put("/api/watches/gambqu", json=outside)
    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "invalid_location", "message": "Select a location inside Arizona"}
    }
    assert "New Mexico" not in response.text
    invalid = client.post("/api/observations", json={**_observation(), "extra": "secret"})
    assert invalid.json()["error"]["message"].startswith("Check the collection inputs")


def test_transaction_failure_rolls_back_and_busy_mutation_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)
    real_create = collection_api.create_observation

    def fail_after_insert(*args: object, **kwargs: object) -> object:
        real_create(*args, **kwargs)  # type: ignore[arg-type]
        raise duckdb.ConstraintException("sensitive database detail")

    monkeypatch.setattr(collection_api, "create_observation", fail_after_insert)
    response = _client(path).post("/api/observations", json=_observation())
    assert response.status_code == 503
    assert "sensitive" not in response.text
    connection = duckdb.connect(str(path), read_only=True)
    assert not connection.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='birding_personal'"
    ).fetchone()
    connection.close()

    app = create_app(database_path=str(path), static_dir=path.parent / "missing")
    asyncio.run(app.state.collection_lock.acquire())
    try:
        busy = TestClient(app).put("/api/watches/gambqu", json=_watch())
    finally:
        app.state.collection_lock.release()
    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "collection_busy"


def test_failed_edit_rolls_back_and_stale_identity_remains_visible(tmp_path: Path) -> None:
    path = _database(tmp_path)
    client = _client(path)
    created = client.post("/api/observations", json=_observation()).json()
    observation_id = created["observation_id"]

    failed = client.put(
        f"/api/observations/{observation_id}", json=_observation(species_code="missing")
    )
    assert failed.status_code == 404
    assert client.get(f"/api/observations/{observation_id}").json()["species_code"] == "gambqu"

    connection = duckdb.connect(str(path))
    connection.execute(
        "DELETE FROM birding_agent.arizona_species_catalog WHERE species_code = 'gambqu'"
    )
    connection.close()
    stale = client.get(f"/api/observations/{observation_id}").json()
    assert stale["identity"] == {
        "catalog_status": "stale",
        "common_name": None,
        "scientific_name": None,
        "taxonomic_category": None,
    }
    assert client.get("/api/birds/gambqu/collection-state").json()["catalog_status"] == "stale"


def test_stale_watch_can_pause_but_cannot_resume(tmp_path: Path) -> None:
    path = _database(tmp_path)
    client = _client(path)
    assert client.put("/api/watches/gambqu", json=_watch()).status_code == 200

    connection = duckdb.connect(str(path))
    connection.execute(
        "DELETE FROM birding_agent.arizona_species_catalog WHERE species_code = 'gambqu'"
    )
    connection.close()

    paused = client.post("/api/watches/gambqu/pause")
    assert paused.status_code == 200
    assert paused.json()["active"] is False
    assert paused.json()["identity"]["catalog_status"] == "stale"
    resume = client.post("/api/watches/gambqu/resume")
    assert resume.status_code == 404
    assert resume.json()["error"]["code"] == "species_not_found"
    assert client.get("/api/watches").json()["watches"][0]["active"] is False

    connection = duckdb.connect(str(path), read_only=True)
    requests = collection_storage.list_watch_cancellation_requests(connection)
    connection.close()
    assert len(requests) == 1
    assert requests[0]["species_code"] == "gambqu"
    assert requests[0]["reason"] == "pause"


def test_watch_replacement_and_cancellation_handoffs_are_idempotent(tmp_path: Path) -> None:
    path = _database(tmp_path)
    client = _client(path)
    created = client.put("/api/watches/gambqu", json=_watch()).json()

    identical = client.put("/api/watches/gambqu", json=_watch()).json()
    assert identical["activated_at"] == created["activated_at"]
    assert identical["updated_at"] == created["updated_at"]

    replaced = client.put("/api/watches/gambqu", json=_watch(30)).json()
    assert replaced["active"] is True
    assert replaced["activated_at"] > created["activated_at"]
    assert replaced["created_at"] == created["created_at"]

    assert client.post("/api/watches/gambqu/pause").status_code == 200
    paused_replacement = client.put("/api/watches/gambqu", json=_watch(35)).json()
    assert paused_replacement["active"] is False
    assert paused_replacement["activated_at"] == replaced["activated_at"]
    assert client.post("/api/watches/gambqu/pause").status_code == 200

    connection = duckdb.connect(str(path))
    requests = collection_storage.list_watch_cancellation_requests(connection)
    assert len(requests) == 1
    assert set(requests[0]) == {
        "cancellation_request_id",
        "species_code",
        "reason",
        "requested_at",
    }
    assert "Phoenix" not in str(requests)
    assert collection_storage.consume_watch_cancellation_request(
        connection, requests[0]["cancellation_request_id"]
    )
    assert not collection_storage.consume_watch_cancellation_request(
        connection, requests[0]["cancellation_request_id"]
    )
    connection.close()

    resumed = client.post("/api/watches/gambqu/resume").json()
    assert resumed["active"] is True
    assert resumed["activated_at"] > replaced["activated_at"]
    connection = duckdb.connect(str(path), read_only=True)
    assert collection_storage.list_watch_cancellation_requests(connection) == []
    connection.close()

    assert client.delete("/api/watches/gambqu").status_code == 200
    assert client.delete("/api/watches/gambqu").status_code == 200
    connection = duckdb.connect(str(path), read_only=True)
    requests = collection_storage.list_watch_cancellation_requests(connection)
    connection.close()
    assert len(requests) == 1
    assert requests[0]["reason"] == "delete"


def test_cancellation_request_and_watch_change_roll_back_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)
    client = _client(path)
    assert client.put("/api/watches/gambqu", json=_watch()).status_code == 200
    real_request = collection_api.request_watch_cancellation

    def fail_after_request(*args: object, **kwargs: object) -> None:
        real_request(*args, **kwargs)  # type: ignore[arg-type]
        raise duckdb.ConstraintException("sensitive cancellation failure")

    monkeypatch.setattr(collection_api, "request_watch_cancellation", fail_after_request)
    response = client.post("/api/watches/gambqu/pause")
    assert response.status_code == 503
    assert "sensitive" not in response.text

    connection = duckdb.connect(str(path), read_only=True)
    assert collection_storage.list_watch_cancellation_requests(connection) == []
    assert collection_storage.list_watches(connection)[0]["active"] is True
    connection.close()


def test_observation_update_advances_updated_at_when_clock_equal_or_regresses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timestamps = iter(
        [
            "2026-07-10T10:00:00+00:00",
            "2026-07-10T10:00:00+00:00",
            "2026-07-10T09:00:00+00:00",
        ]
    )
    monkeypatch.setattr(collection_storage, "_now", lambda: next(timestamps))
    client = _client(_database(tmp_path))
    created = client.post("/api/observations", json=_observation()).json()
    equal_clock = client.put(
        f"/api/observations/{created['observation_id']}",
        json={**_observation(), "notes": "Updated once"},
    ).json()
    regressed_clock = client.put(
        f"/api/observations/{created['observation_id']}",
        json={**_observation(), "notes": "Updated twice"},
    ).json()
    assert equal_clock["created_at"] == regressed_clock["created_at"] == created["created_at"]
    assert _timestamp(created["updated_at"]) < _timestamp(equal_clock["updated_at"])
    assert _timestamp(equal_clock["updated_at"]) < _timestamp(regressed_clock["updated_at"])


def test_watch_generation_and_timestamps_do_not_depend_on_wall_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(collection_storage, "_now", lambda: "2026-07-10T10:00:00+00:00")
    path = _database(tmp_path)
    client = _client(path)
    created = client.put("/api/watches/gambqu", json=_watch()).json()
    connection = duckdb.connect(str(path), read_only=True)
    first_identity = connection.execute(
        """SELECT watch_id, activation_generation FROM birding_personal.watches
           WHERE species_code = 'gambqu'"""
    ).fetchone()
    connection.close()
    assert first_identity is not None
    assert not {"watch_id", "activation_generation"} & set(created)

    identical = client.put("/api/watches/gambqu", json=_watch()).json()
    assert identical == created
    changed = client.put("/api/watches/gambqu", json=_watch(30)).json()
    assert changed["created_at"] == created["created_at"]
    assert _timestamp(changed["updated_at"]) > _timestamp(created["updated_at"])
    assert _timestamp(changed["activated_at"]) > _timestamp(created["activated_at"])

    connection = duckdb.connect(str(path), read_only=True)
    changed_identity = connection.execute(
        """SELECT watch_id, activation_generation FROM birding_personal.watches
           WHERE species_code = 'gambqu'"""
    ).fetchone()
    connection.close()
    assert changed_identity is not None
    assert changed_identity[0] == first_identity[0]
    assert changed_identity[1] != first_identity[1]

    first_pause = client.post("/api/watches/gambqu/pause").json()
    resumed = client.post("/api/watches/gambqu/resume").json()
    second_pause = client.post("/api/watches/gambqu/pause").json()
    assert _timestamp(changed["updated_at"]) < _timestamp(first_pause["updated_at"])
    assert _timestamp(first_pause["updated_at"]) < _timestamp(resumed["updated_at"])
    assert _timestamp(resumed["updated_at"]) < _timestamp(second_pause["updated_at"])
    assert _timestamp(resumed["activated_at"]) > _timestamp(changed["activated_at"])

    connection = duckdb.connect(str(path), read_only=True)
    requests = collection_storage.list_watch_cancellation_requests(connection)
    second_identity = connection.execute(
        """SELECT watch_id, activation_generation FROM birding_personal.watches
           WHERE species_code = 'gambqu'"""
    ).fetchone()
    connection.close()
    assert second_identity is not None
    assert second_identity[0] == first_identity[0]
    assert second_identity[1] != changed_identity[1]
    assert [request["reason"] for request in requests] == ["pause", "pause"]
    assert len({request["cancellation_request_id"] for request in requests}) == 2


def _drop_runtime_identity_columns(path: Path) -> None:
    connection = duckdb.connect(str(path))
    connection.execute(
        "ALTER TABLE birding_personal.watch_cancellation_requests DROP COLUMN activation_generation"
    )
    connection.execute(
        "ALTER TABLE birding_personal.watch_cancellation_requests DROP COLUMN watch_id"
    )
    connection.execute("ALTER TABLE birding_personal.watches DROP COLUMN activation_generation")
    connection.execute("ALTER TABLE birding_personal.watches DROP COLUMN watch_id")
    connection.close()


def test_legacy_watch_identity_migration_is_private_and_transactional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)
    client = _client(path)
    assert client.put("/api/watches/gambqu", json=_watch()).status_code == 200
    assert client.post("/api/watches/gambqu/pause").status_code == 200
    _drop_runtime_identity_columns(path)

    real_add_column = collection_storage._add_opaque_column
    calls = 0

    def fail_during_migration(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        real_add_column(*args, **kwargs)  # type: ignore[arg-type]
        if calls == 1:
            raise duckdb.ConstraintException("migration failure")

    monkeypatch.setattr(collection_storage, "_add_opaque_column", fail_during_migration)
    failed_migration = client.put("/api/watches/gambqu", json=_watch(30))
    assert failed_migration.status_code == 503
    connection = duckdb.connect(str(path), read_only=True)
    failed_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info('birding_personal.watches')").fetchall()
    }
    connection.close()
    assert not {"watch_id", "activation_generation"} & failed_columns
    monkeypatch.setattr(collection_storage, "_add_opaque_column", real_add_column)

    migrated = client.put("/api/watches/gambqu", json=_watch(30))
    assert migrated.status_code == 200
    assert not {"watch_id", "activation_generation"} & set(migrated.json())
    connection = duckdb.connect(str(path), read_only=True)
    watch_identity = connection.execute(
        "SELECT watch_id, activation_generation FROM birding_personal.watches"
    ).fetchone()
    migrated_columns = {
        row[1]: bool(row[3])
        for row in connection.execute("PRAGMA table_info('birding_personal.watches')").fetchall()
    }
    request_identity = connection.execute(
        """SELECT watch_id, activation_generation
           FROM birding_personal.watch_cancellation_requests"""
    ).fetchone()
    connection.close()
    assert watch_identity is not None and request_identity == watch_identity
    assert migrated_columns["watch_id"] and migrated_columns["activation_generation"]

    _drop_runtime_identity_columns(path)
    real_put = collection_api.put_watch

    def fail_after_put(*args: object, **kwargs: object) -> object:
        real_put(*args, **kwargs)  # type: ignore[arg-type]
        raise duckdb.ConstraintException("migration rollback")

    monkeypatch.setattr(collection_api, "put_watch", fail_after_put)
    failed = client.put("/api/watches/gambqu", json=_watch(35))
    assert failed.status_code == 503
    connection = duckdb.connect(str(path), read_only=True)
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info('birding_personal.watches')").fetchall()
    }
    radius = connection.execute(
        "SELECT radius_miles FROM birding_personal.watches WHERE species_code = 'gambqu'"
    ).fetchone()
    connection.close()
    assert {"watch_id", "activation_generation"} <= columns
    assert radius == (30.0,)


def _prepare_multirow_legacy_cancellations(path: Path) -> list[str]:
    client = _client(path)
    assert client.put("/api/watches/gambqu", json=_watch()).status_code == 200
    assert client.post("/api/watches/gambqu/pause").status_code == 200
    connection = duckdb.connect(str(path))
    current_id = str(
        connection.execute(
            "SELECT cancellation_request_id FROM birding_personal.watch_cancellation_requests"
        ).fetchone()[0]
    )
    connection.execute(
        """UPDATE birding_personal.watch_cancellation_requests
           SET cancellation_request_id = 'legacy-current-newest',
               requested_at = '2026-01-03T00:00:00+00:00'"""
    )
    legacy_ids = [
        "legacy-current-older",
        "legacy-orphan-older",
        "legacy-orphan-newer",
        "legacy-current-newest",
    ]
    connection.execute(
        """INSERT INTO birding_personal.watch_cancellation_requests VALUES
           ('legacy-current-older', 'gambqu', 'old-watch', 'old-generation',
            'pause', '2026-01-01T00:00:00+00:00'),
           ('legacy-orphan-older', 'sxrgoo1', 'orphan-watch-1', 'orphan-generation-1',
            'pause', '2026-01-01T00:00:00+00:00'),
           ('legacy-orphan-newer', 'sxrgoo1', 'orphan-watch-2', 'orphan-generation-2',
            'delete', '2026-01-02T00:00:00+00:00')"""
    )
    assert current_id not in legacy_ids
    connection.close()
    _drop_runtime_identity_columns(path)
    return legacy_ids


def test_legacy_cancellation_migration_preserves_transitions_and_dedupes_current(
    tmp_path: Path,
) -> None:
    path = _database(tmp_path)
    _prepare_multirow_legacy_cancellations(path)
    client = _client(path)
    assert client.put("/api/watches/gambqu", json=_watch()).status_code == 200

    connection = duckdb.connect(str(path))
    current = connection.execute(
        """SELECT watch_id, activation_generation
           FROM birding_personal.watches WHERE species_code = 'gambqu'"""
    ).fetchone()
    assert current is not None
    rows = connection.execute(
        """SELECT cancellation_request_id, species_code, watch_id,
                  activation_generation, reason, requested_at
           FROM birding_personal.watch_cancellation_requests
           ORDER BY species_code, requested_at, cancellation_request_id"""
    ).fetchall()
    assert len(rows) == 4
    assert len({(str(row[2]), str(row[3]), str(row[4])) for row in rows}) == 4

    gambel_rows = [row for row in rows if row[1] == "gambqu"]
    newest = max(gambel_rows, key=lambda row: (str(row[5]), str(row[0])))
    older = min(gambel_rows, key=lambda row: (str(row[5]), str(row[0])))
    expected_id = collection_storage._cancellation_request_id(
        str(current[0]), str(current[1]), "pause"
    )
    assert newest[0] == expected_id
    assert newest[2:4] == current
    assert older[2:4] != current

    orphan_rows = [row for row in rows if row[1] == "sxrgoo1"]
    assert len(orphan_rows) == 2
    assert orphan_rows[0][2:4] != orphan_rows[1][2:4]

    before = rows
    collection_storage.request_watch_cancellation(
        connection,
        "gambqu",
        reason="pause",
        watch_id=str(current[0]),
        activation_generation=str(current[1]),
    )
    assert connection.execute(
        "SELECT count(*) FROM birding_personal.watch_cancellation_requests"
    ).fetchone() == (4,)
    connection.execute("BEGIN TRANSACTION")
    collection_storage.backfill_runtime_identities(connection)
    connection.execute("COMMIT")
    after = connection.execute(
        """SELECT cancellation_request_id, species_code, watch_id,
                  activation_generation, reason, requested_at
           FROM birding_personal.watch_cancellation_requests
           ORDER BY species_code, requested_at, cancellation_request_id"""
    ).fetchall()
    connection.close()
    assert after == before


def test_legacy_cancellation_backfill_rolls_back_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)
    legacy_ids = _prepare_multirow_legacy_cancellations(path)
    client = _client(path)
    real_apply = collection_storage._apply_legacy_request_mapping
    calls = 0

    def fail_second_mapping(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        real_apply(*args, **kwargs)  # type: ignore[arg-type]
        if calls == 2:
            raise duckdb.ConstraintException("legacy backfill rollback")

    monkeypatch.setattr(collection_storage, "_apply_legacy_request_mapping", fail_second_mapping)
    failed = client.put("/api/watches/gambqu", json=_watch())
    assert failed.status_code == 503
    connection = duckdb.connect(str(path), read_only=True)
    rolled_back = connection.execute(
        """SELECT cancellation_request_id, watch_id, activation_generation
           FROM birding_personal.watch_cancellation_requests
           ORDER BY cancellation_request_id"""
    ).fetchall()
    connection.close()
    assert [str(row[0]) for row in rolled_back] == sorted(legacy_ids)
    assert all(row[1] is None and row[2] is None for row in rolled_back)

    monkeypatch.setattr(collection_storage, "_apply_legacy_request_mapping", real_apply)
    assert client.put("/api/watches/gambqu", json=_watch()).status_code == 200
    connection = duckdb.connect(str(path), read_only=True)
    resumed = connection.execute(
        """SELECT cancellation_request_id, watch_id, activation_generation
           FROM birding_personal.watch_cancellation_requests"""
    ).fetchall()
    connection.close()
    assert len(resumed) == 4
    assert len({(str(row[1]), str(row[2])) for row in resumed}) == 4


@pytest.mark.parametrize("orphan", [False, True], ids=["current", "orphan"])
def test_legacy_identity_conflicts_are_safe_repeatable_and_rolled_back(
    tmp_path: Path, orphan: bool
) -> None:
    path = _database(tmp_path)
    client = _client(path)
    species_code = "sxrgoo1" if orphan else "gambqu"
    assert client.put(f"/api/watches/{species_code}", json=_watch()).status_code == 200
    if orphan:
        assert client.delete(f"/api/watches/{species_code}").status_code == 200
    else:
        assert client.post(f"/api/watches/{species_code}/pause").status_code == 200

    connection = duckdb.connect(str(path))
    request = connection.execute(
        """SELECT cancellation_request_id, watch_id, activation_generation, reason
           FROM birding_personal.watch_cancellation_requests
           WHERE species_code = ?""",
        [species_code],
    ).fetchone()
    assert request is not None
    original_id, watch_id, generation, reason = map(str, request)
    legacy_id = f"legacy-{species_code}"
    if orphan:
        target_watch_id = collection_storage._legacy_identity("watch", legacy_id)
        target_generation = collection_storage._legacy_identity("activation", legacy_id)
        target_id = collection_storage._cancellation_request_id(
            target_watch_id, target_generation, reason
        )
    else:
        target_id = collection_storage._cancellation_request_id(watch_id, generation, reason)
        assert target_id == original_id

    for column in ("watch_id", "activation_generation"):
        connection.execute(
            f"""ALTER TABLE birding_personal.watch_cancellation_requests
                ALTER COLUMN {column} DROP NOT NULL"""
        )
    connection.execute(
        """UPDATE birding_personal.watch_cancellation_requests
           SET cancellation_request_id = ?, watch_id = NULL, activation_generation = NULL
           WHERE cancellation_request_id = ?""",
        [legacy_id, original_id],
    )
    connection.execute(
        """INSERT INTO birding_personal.watch_cancellation_requests VALUES
           (?, 'conflicting', 'conflicting-watch', 'conflicting-generation',
            'delete', '2026-01-01T00:00:00+00:00')""",
        [target_id],
    )
    connection.close()

    if orphan:
        request_path = "/api/observations"
        request_body = _observation()
        responses = [
            client.post(request_path, json=request_body),
            client.post(request_path, json=request_body),
        ]
    else:
        responses = [
            client.put(f"/api/watches/{species_code}", json=_watch()),
            client.put(f"/api/watches/{species_code}", json=_watch()),
        ]

    for response in responses:
        assert response.status_code == 503
        assert response.json() == {
            "error": {
                "code": "database_unavailable",
                "message": "The local collection is unavailable",
            }
        }
        assert not {
            legacy_id,
            target_id,
            "conflicting-watch",
            "conflicting-generation",
        } & set(response.text.split())

    connection = duckdb.connect(str(path), read_only=True)
    rows = connection.execute(
        """SELECT cancellation_request_id, watch_id, activation_generation
           FROM birding_personal.watch_cancellation_requests
           ORDER BY cancellation_request_id"""
    ).fetchall()
    observation_count = connection.execute(
        "SELECT count(*) FROM birding_personal.observations"
    ).fetchone()
    connection.close()
    legacy_row = next(row for row in rows if row[0] == legacy_id)
    assert legacy_row[1:] == (None, None)
    assert any(row[0] == target_id for row in rows)
    assert observation_count == (0,)


def test_runtime_schema_constraints_and_no_downstream_side_effect_tables(tmp_path: Path) -> None:
    path = _database(tmp_path)
    assert _client(path).post("/api/observations", json=_observation()).status_code == 201
    connection = duckdb.connect(str(path), read_only=True)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='birding_personal'"
        ).fetchall()
    }
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info('birding_personal.watches')").fetchall()
    }
    connection.close()
    assert tables == {
        "observations",
        "watches",
        "watch_cancellation_requests",
    }
    assert {
        "watch_id",
        "activation_generation",
        "active",
        "activated_at",
        "radius_miles",
        "center_latitude",
    } <= columns
    assert not {"matches", "outbox", "calendar_events", "smtp_attempts"} & tables


def _selected_location(
    *,
    display_name: str = "Watson Lake and Riparian Preserve",
    source: str = "ebird_hotspot",
    source_id: str = "L270303",
    latitude: float = 34.5822319,
    longitude: float = -112.4259328,
) -> dict[str, object]:
    return {
        "display_name": display_name,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "America/Phoenix",
        "region_code": "US-AZ",
        "source": source,
        "source_id": source_id,
        "place_type": "Birding hotspot" if source == "ebird_hotspot" else "Arizona place",
    }


def test_structured_observation_location_create_clear_and_replace(tmp_path: Path) -> None:
    path = _database(tmp_path)
    client = _client(path)
    selected = _selected_location()
    created = client.post(
        "/api/observations",
        json={
            **_observation(),
            "location": selected["display_name"],
            "location_selection": selected,
        },
    )
    assert created.status_code == 201
    row = created.json()
    assert {
        key: row[key]
        for key in (
            "location",
            "location_source",
            "location_source_id",
            "location_latitude",
            "location_longitude",
            "location_timezone",
            "location_region_code",
        )
    } == {
        "location": "Watson Lake and Riparian Preserve",
        "location_source": "ebird_hotspot",
        "location_source_id": "L270303",
        "location_latitude": 34.5822319,
        "location_longitude": -112.4259328,
        "location_timezone": "America/Phoenix",
        "location_region_code": "US-AZ",
    }

    observation_id = row["observation_id"]
    cleared = client.put(
        f"/api/observations/{observation_id}",
        json={**_observation(), "location": "Back yard"},
    )
    assert cleared.status_code == 200
    assert cleared.json()["location"] == "Back yard"
    assert all(
        cleared.json()[key] is None
        for key in (
            "location_source",
            "location_source_id",
            "location_latitude",
            "location_longitude",
            "location_timezone",
            "location_region_code",
        )
    )

    replacement = _selected_location(
        display_name="Prescott, Arizona, United States",
        source="open_meteo",
        source_id="open_meteo_5309842",
        latitude=34.54002,
        longitude=-112.4685,
    )
    replaced = client.put(
        f"/api/observations/{observation_id}",
        json={
            **_observation(),
            "location": replacement["display_name"],
            "location_selection": replacement,
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["location_source"] == "open_meteo"
    assert replaced.json()["location_source_id"] == "open_meteo_5309842"


def test_structured_observation_storage_and_service_reject_partial_state(tmp_path: Path) -> None:
    path = _database(tmp_path)
    connection = duckdb.connect(str(path))
    collection_storage.ensure_tables(connection)
    with pytest.raises(ValueError, match="all-or-none"):
        collection_storage.create_observation(
            connection,
            species_code="gambqu",
            observation_date=date(2026, 7, 9),
            location_text="Watson Lake",
            notes=None,
            location_source="ebird_hotspot",
        )
    assert connection.execute("SELECT COUNT(*) FROM birding_personal.observations").fetchone() == (
        0,
    )
    with pytest.raises(duckdb.ConstraintException):
        connection.execute(
            """
            INSERT INTO birding_personal.observations (
                observation_id, species_code, observation_date, location_text, notes,
                created_at, updated_at, location_source
            ) VALUES ('partial', 'gambqu', DATE '2026-07-09', 'Watson Lake', NULL,
                      '2026-07-09T12:00:00+00:00', '2026-07-09T12:00:00+00:00',
                      'ebird_hotspot')
            """
        )
    assert connection.execute("SELECT COUNT(*) FROM birding_personal.observations").fetchone() == (
        0,
    )
    connection.close()


def test_structured_observation_location_attacks_rollback(tmp_path: Path) -> None:
    path = _database(tmp_path)
    client = _client(path)
    baseline = client.post("/api/observations", json={**_observation(), "location": "Back yard"})
    assert baseline.status_code == 201
    before = client.get("/api/observations").json()
    selected = _selected_location()
    attacks = [
        {**_observation(), "location": "Wrong name", "location_selection": selected},
        {
            **_observation(),
            "location": selected["display_name"],
            "location_selection": {**selected, "latitude": 40.0},
        },
        {
            **_observation(),
            "location": selected["display_name"],
            "location_selection": {**selected, "source": "private_observation"},
        },
        {
            **_observation(),
            "location": selected["display_name"],
            "location_selection": {**selected, "place_type": "Arizona place"},
        },
        {
            **_observation(),
            "location": selected["display_name"],
            "location_source": "ebird_hotspot",
        },
    ]
    for payload in attacks:
        response = client.post("/api/observations", json=payload)
        assert response.status_code == 422
        assert "L270303" not in response.text
        assert client.get("/api/observations").json() == before


def test_legacy_location_migration_is_idempotent_private_and_transactional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA birding_personal")
    connection.execute(
        """
        CREATE TABLE birding_personal.observations (
            observation_id VARCHAR PRIMARY KEY, species_code VARCHAR NOT NULL,
            observation_date DATE NOT NULL, location_text VARCHAR, notes VARCHAR,
            created_at VARCHAR NOT NULL, updated_at VARCHAR NOT NULL
        )
        """
    )
    legacy = (
        "legacy-observation",
        "gambqu",
        "2026-07-09",
        "prescott",
        None,
        "2026-07-09T12:00:00+00:00",
        "2026-07-09T12:00:00+00:00",
    )
    connection.execute(
        "INSERT INTO birding_personal.observations VALUES (?, ?, ?, ?, ?, ?, ?)", legacy
    )
    connection.close()

    client = _client(path)
    read_before = client.get("/api/observations").json()["observations"][0]
    assert read_before["location"] == "prescott"
    assert read_before["location_source"] is None

    original_add = collection_storage._add_observation_location_columns

    def fail_after_one_column(connection: duckdb.DuckDBPyConnection) -> None:
        connection.execute(
            "ALTER TABLE birding_personal.observations ADD COLUMN location_source VARCHAR"
        )
        raise duckdb.ConstraintException("structured location migration rollback")

    monkeypatch.setattr(
        collection_storage, "_add_observation_location_columns", fail_after_one_column
    )
    failed = client.put(
        "/api/observations/legacy-observation", json={**_observation(), "location": "prescott"}
    )
    assert failed.status_code == 503
    connection = duckdb.connect(str(path), read_only=True)
    assert "location_source" not in {
        row[0] for row in connection.execute("DESCRIBE birding_personal.observations").fetchall()
    }
    rolled_back = connection.execute("SELECT * FROM birding_personal.observations").fetchone()
    assert rolled_back is not None
    assert (rolled_back[0], rolled_back[1], str(rolled_back[2]), *rolled_back[3:]) == legacy
    connection.close()

    monkeypatch.setattr(collection_storage, "_add_observation_location_columns", original_add)
    migrated = client.put(
        "/api/observations/legacy-observation", json={**_observation(), "location": "prescott"}
    )
    assert migrated.status_code == 200
    connection = duckdb.connect(str(path))
    migration_sql = Path("migrations/20260711_structured_observation_locations.sql").read_text()
    connection.execute(migration_sql)
    connection.execute(migration_sql)
    stored = connection.execute(
        """
        SELECT observation_id, location_text, location_source, location_source_id,
               location_latitude, location_longitude, location_timezone, location_region_code
        FROM birding_personal.observations
        """
    ).fetchone()
    connection.close()
    assert stored == ("legacy-observation", "prescott", None, None, None, None, None, None)

    private_id = "L_PRIVATE_TEST"
    created = client.post(
        "/api/observations",
        json={
            **_observation(),
            "location": "Watson Lake and Riparian Preserve",
            "location_selection": {**_selected_location(), "source_id": private_id},
        },
    )
    assert created.status_code == 201
    assert private_id in created.text
    assert private_id in client.get("/api/observations").text
    assert private_id not in client.get("/api/birds").text
    assert private_id not in client.get("/api/life-list").text
