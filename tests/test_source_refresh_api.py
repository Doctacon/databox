from __future__ import annotations

from pathlib import Path

from databox import source_refresh_api
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeProcess:
    pid = 424242

    def __init__(self, *_: object, **__: object) -> None:
        pass

    def wait(self) -> int:
        return 0


def app(path: Path) -> TestClient:
    value = FastAPI()
    source_refresh_api.register_source_refresh_routes(value, status_path=path)
    return TestClient(value, base_url="http://127.0.0.1")


def test_status_is_read_only_and_launch_is_same_origin_confirmed(
    tmp_path: Path, monkeypatch
) -> None:
    status = tmp_path / "status.json"
    client = app(status)
    assert client.get("/api/source-refresh").json()["state"] == "idle"
    assert not status.exists()
    assert (
        client.post(
            "/api/source-refresh", json={"confirm": True}, headers={"host": "evil.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/source-refresh", json={"confirm": False}).status_code == 422
    monkeypatch.setattr(source_refresh_api.subprocess, "Popen", FakeProcess)
    response = client.post("/api/source-refresh", json={"confirm": True})
    assert response.status_code == 202
    assert response.json()["sources"] == list(source_refresh_api.ROUTINE_SOURCES)
    assert response.json()["state"] == "running_sources"


def test_atomic_status_validation_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "status.json"
    path.write_text('{"state":"running_sources","secret":"leak"}')
    assert app(path).get("/api/source-refresh").json()["state"] == "idle"
