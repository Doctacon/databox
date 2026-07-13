from __future__ import annotations

import json
import signal
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from databox import source_refresh_api
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeProcess:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def __init__(self, command: list[str], **kwargs: object) -> None:
        self.calls.append((command, kwargs))

    def wait(self) -> int:
        return 0


def app(path: Path) -> TestClient:
    value = FastAPI()
    source_refresh_api.register_source_refresh_routes(value, status_path=path)
    return TestClient(value, base_url="http://127.0.0.1")


def running_status(path: Path, run_id: str) -> dict[str, object]:
    current = source_refresh_api.idle_status()
    current.update(
        run_id=run_id,
        state="running_sources",
        started_at=datetime.now(UTC).isoformat(),
        safe_message="Refreshing routine sources",
        log_name="rufous-source-refresh.log",
    )
    source_refresh_api.write_status(path, current)
    return current


def test_status_is_read_only_and_launch_is_same_origin_confirmed(
    tmp_path: Path, monkeypatch
) -> None:
    status = tmp_path / "status.json"
    client = app(status)
    assert client.get("/api/source-refresh").json()["state"] == "idle"
    assert not status.exists()
    for headers in ({"host": "evil.example"}, {"origin": "http://evil.example"}):
        assert (
            client.post("/api/source-refresh", json={"confirm": True}, headers=headers).status_code
            == 403
        )
    assert client.post("/api/source-refresh", json={"confirm": False}).status_code == 422
    assert (
        client.post("/api/source-refresh", json={"confirm": True, "source": "avonet"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/source-refresh",
            content="confirm=true",
            headers={"content-type": "application/x-www-form-urlencoded"},
        ).status_code
        == 422
    )

    FakeProcess.calls.clear()
    monkeypatch.setattr(source_refresh_api.subprocess, "Popen", FakeProcess)
    response = client.post("/api/source-refresh", json={"confirm": True})
    assert response.status_code == 202
    assert [item["name"] for item in response.json()["sources"]] == list(
        source_refresh_api.ROUTINE_SOURCES
    )
    command, options = FakeProcess.calls[0]
    assert command[:3] == [
        str(source_refresh_api.PROJECT_ROOT / ".venv" / "bin" / "python"),
        "-m",
        "databox.source_refresh_runner",
    ]
    assert "--owner" in command
    source_arguments = [
        command[index + 1] for index, value in enumerate(command[:-1]) if value == "--source"
    ]
    assert source_arguments == list(source_refresh_api.ROUTINE_SOURCES)
    assert source_arguments == [
        source.name for source in source_refresh_api.SOURCES if source.parallel_refresh
    ]
    environment = options["env"]
    assert isinstance(environment, dict)
    assert environment["DAGSTER_HOME"] == str(source_refresh_api.PROJECT_ROOT / ".dagster")
    assert environment["RUNTIME__DLTHUB_TELEMETRY"] == "false"
    assert environment["SQLMESH__DISABLE_ANONYMIZED_ANALYTICS"] == "true"
    assert client.post("/api/source-refresh", json={"confirm": True}).status_code == 409


def test_atomic_owner_blocks_invalid_status_and_pre_runner_publication(tmp_path: Path) -> None:
    path = tmp_path / "status.json"
    owner = path.with_suffix(".owner")
    run_id = "refresh_" + "a" * 32
    source_refresh_api.create_owner(owner, run_id)
    path.write_text('{"state":"running_sources","secret":"leak"}')
    client = app(path)
    assert client.get("/api/source-refresh").json()["state"] == "idle"
    assert client.post("/api/source-refresh", json={"confirm": True}).status_code == 409
    value = source_refresh_api.read_owner(owner)
    assert value is not None and value["pid"] is None


def test_mismatched_owner_fails_closed_without_releasing_new_run(tmp_path: Path) -> None:
    path = tmp_path / "status.json"
    running_status(path, "refresh_" + "1" * 32)
    owner = path.with_suffix(".owner")
    source_refresh_api.create_owner(owner, "refresh_" + "2" * 32)
    client = app(path)
    assert client.get("/api/source-refresh").json()["state"] == "running_sources"
    assert client.post("/api/source-refresh", json={"confirm": True}).status_code == 409
    assert source_refresh_api.read_owner(owner)["run_id"] == "refresh_" + "2" * 32


def test_stale_heartbeat_recovers_even_when_pid_is_live_but_mismatched(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "status.json"
    owner = path.with_suffix(".owner")
    run_id = "refresh_" + "b" * 32
    running_status(path, run_id)
    stale = source_refresh_api.owner_value(run_id, pid=1)
    stale["heartbeat_at"] = (
        datetime.now(UTC) - timedelta(seconds=source_refresh_api.OWNER_STALE_SECONDS + 1)
    ).isoformat()
    source_refresh_api.write_owner(owner, stale)
    monkeypatch.setattr(source_refresh_api, "_owner_process_matches", lambda _: False)
    recovered = app(path).get("/api/source-refresh").json()
    assert recovered["state"] == "failed"
    assert "stopped unexpectedly" in recovered["safe_message"]
    assert not owner.exists()


def test_stale_heartbeat_keeps_verified_runner_owner_active(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "status.json"
    owner = path.with_suffix(".owner")
    run_id = "refresh_" + "f" * 32
    running_status(path, run_id)
    stale = source_refresh_api.owner_value(run_id, pid=99999)
    stale["heartbeat_at"] = "2026-01-01T00:00:00+00:00"
    source_refresh_api.write_owner(owner, stale)
    monkeypatch.setattr(source_refresh_api, "_owner_process_matches", lambda _: True)
    client = app(path)
    assert client.get("/api/source-refresh").json()["state"] == "running_sources"
    assert client.post("/api/source-refresh", json={"confirm": True}).status_code == 409


def test_terminal_status_survives_app_restart_without_owner(tmp_path: Path) -> None:
    path = tmp_path / "status.json"
    current = source_refresh_api.idle_status()
    current.update(
        run_id="refresh_" + "c" * 32,
        state="succeeded",
        sources=[
            {"name": name, "status": "succeeded"} for name in source_refresh_api.ROUTINE_SOURCES
        ],
        started_at="2026-07-12T12:00:00+00:00",
        finished_at="2026-07-12T12:02:00+00:00",
        safe_message="Routine source refresh completed",
        log_name="rufous-source-refresh.log",
    )
    source_refresh_api.write_status(path, current)
    assert app(path).get("/api/source-refresh").json() == current


def test_spawn_failure_releases_owner_and_persists_safe_failure(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "status.json"

    def fail(*args, **kwargs):
        raise OSError("private raw launch detail")

    monkeypatch.setattr(source_refresh_api.subprocess, "Popen", fail)
    response = app(path).post("/api/source-refresh", json={"confirm": True})
    assert response.status_code == 202
    assert response.json()["state"] == "failed"
    assert response.json()["safe_message"] == "Routine source refresh could not start"
    assert not path.with_suffix(".owner").exists()


def test_backend_status_rejects_contract_malformed_values() -> None:
    valid = source_refresh_api.idle_status()
    invalid = [
        {**valid, "sources": []},
        {**valid, "sources": list(reversed(valid["sources"]))},
        {**valid, "sources": [valid["sources"][0], *valid["sources"][1:-1], valid["sources"][0]]},
        {**valid, "run_id": "refresh_bad", "state": "running_sources"},
        {
            **valid,
            "run_id": "refresh_" + "a" * 32,
            "state": "running_sources",
            "started_at": "not-a-time",
            "safe_message": "running",
            "log_name": "rufous-source-refresh.log",
        },
        {
            **valid,
            "run_id": "refresh_" + "a" * 32,
            "state": "running_sources",
            "started_at": datetime.now(UTC).isoformat(),
            "safe_message": "x" * 201,
            "log_name": "rufous-source-refresh.log",
        },
        {
            **valid,
            "run_id": "refresh_" + "a" * 32,
            "state": "running_sources",
            "started_at": datetime.now(UTC).isoformat(),
            "safe_message": "running",
            "log_name": "../refresh.log",
        },
    ]
    for value in invalid:
        with pytest.raises(ValueError):
            source_refresh_api.RefreshStatus.model_validate(value)


def test_get_rechecks_status_before_failure_publication(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "status.json"
    run_id = "refresh_" + "7" * 32
    running = running_status(path, run_id)
    terminal = {
        **running,
        "state": "succeeded",
        "sources": [
            {"name": name, "status": "succeeded"} for name in source_refresh_api.ROUTINE_SOURCES
        ],
        "finished_at": datetime.now(UTC).isoformat(),
        "safe_message": "Routine source refresh completed",
    }
    reads = iter((running, terminal))
    monkeypatch.setattr(source_refresh_api, "read_status", lambda _: next(reads))
    response = app(path).get("/api/source-refresh")
    assert response.json()["state"] == "succeeded"
    assert json.loads(path.read_text())["state"] == "running_sources"


def test_terminal_write_wins_interleaving_with_recovery_cas(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "status.json"
    run_id = "refresh_" + "6" * 32
    running = running_status(path, run_id)
    terminal = {
        **running,
        "state": "succeeded",
        "sources": [
            {"name": name, "status": "succeeded"} for name in source_refresh_api.ROUTINE_SOURCES
        ],
        "finished_at": datetime.now(UTC).isoformat(),
        "safe_message": "Routine source refresh completed",
    }
    inspected = threading.Event()
    continue_recovery = threading.Event()
    original = source_refresh_api._write_status_unlocked

    def paused_write(target: Path, value: dict[str, object]) -> None:
        if value.get("state") == "failed":
            inspected.set()
            assert continue_recovery.wait(timeout=2)
        original(target, value)

    monkeypatch.setattr(source_refresh_api, "_write_status_unlocked", paused_write)
    recovery = threading.Thread(
        target=source_refresh_api.fail_running_status,
        args=(path, run_id, "Source refresh process stopped unexpectedly; inspect the local log"),
    )
    recovery.start()
    assert inspected.wait(timeout=2)
    terminal_writer = threading.Thread(
        target=source_refresh_api.write_status, args=(path, terminal)
    )
    terminal_writer.start()
    assert terminal_writer.is_alive()
    continue_recovery.set()
    recovery.join(timeout=2)
    terminal_writer.join(timeout=2)
    assert not recovery.is_alive() and not terminal_writer.is_alive()
    assert source_refresh_api.read_status(path)["state"] == "succeeded"


def test_missing_gate_leader_with_surviving_group_stays_fail_closed(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "status.json"
    owner_path = path.with_suffix(".owner")
    run_id = "refresh_" + "5" * 32
    running_status(path, run_id)
    owner = source_refresh_api.owner_value(run_id, pid=111, child_pid=222)
    owner["heartbeat_at"] = "2026-01-01T00:00:00+00:00"
    source_refresh_api.write_owner(owner_path, owner)
    monkeypatch.setattr(source_refresh_api, "_owner_process_matches", lambda _: False)
    monkeypatch.setattr(source_refresh_api, "_child_process_matches", lambda _: False)
    monkeypatch.setattr(source_refresh_api, "process_group_exists", lambda _: True)
    client = app(path)
    assert client.get("/api/source-refresh").json()["state"] == "running_sources"
    assert client.post("/api/source-refresh", json={"confirm": True}).status_code == 409
    assert owner_path.exists()


def test_real_missing_leader_with_sigterm_ignoring_descendant_stays_locked(
    tmp_path: Path,
) -> None:
    status = tmp_path / "status.json"
    owner_path = status.with_suffix(".owner")
    run_id = "refresh_" + "6" * 32
    running_status(status, run_id)
    ready = tmp_path / "descendant-ready"
    child_code = (
        "import pathlib,signal,sys,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "pathlib.Path(sys.argv[1]).write_text('ready'); time.sleep(30)"
    )
    leader_code = (
        "import pathlib,subprocess,sys,time\n"
        "ready=sys.argv[1]\n"
        f"child={child_code!r}\n"
        "subprocess.Popen([sys.executable,'-c',child,ready])\n"
        "while not pathlib.Path(ready).exists(): time.sleep(0.01)\n"
    )
    leader = subprocess.Popen(
        [sys.executable, "-c", leader_code, str(ready)],
        start_new_session=True,
    )
    process_group_id = leader.pid
    try:
        assert leader.wait(timeout=5) == 0
        assert ready.exists()
        assert source_refresh_api.process_group_exists(process_group_id) is True
        owner = source_refresh_api.owner_value(
            run_id,
            pid=leader.pid,
            child_pid=process_group_id,
        )
        owner["heartbeat_at"] = "2026-01-01T00:00:00+00:00"
        source_refresh_api.write_owner(owner_path, owner)

        client = app(status)
        assert client.get("/api/source-refresh").json()["state"] == "running_sources"
        assert client.post("/api/source-refresh", json={"confirm": True}).status_code == 409
        assert owner_path.exists()
    finally:
        try:
            source_refresh_api.os.killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for _ in range(100):
            if source_refresh_api.process_group_exists(process_group_id) is False:
                break
            time.sleep(0.02)
        assert source_refresh_api.process_group_exists(process_group_id) is False


def test_orphan_release_requires_whole_group_exit(monkeypatch) -> None:
    run_id = "refresh_" + "4" * 32
    owner = source_refresh_api.owner_value(run_id, pid=111, child_pid=222)
    signals: list[int] = []
    waits = iter((False, True))
    monkeypatch.setattr(source_refresh_api, "owner_state", lambda _: "orphan")
    monkeypatch.setattr(source_refresh_api, "_wait_for_group_exit", lambda _: next(waits))
    monkeypatch.setattr(
        source_refresh_api.os,
        "killpg",
        lambda pid, sig: signals.append(sig),
    )
    assert source_refresh_api.stop_orphan(owner)
    assert signals == [signal.SIGTERM, signal.SIGKILL]


def test_abrupt_runner_death_stops_durable_gate_before_retry(tmp_path: Path, monkeypatch) -> None:
    status = tmp_path / "status.json"
    owner = status.with_suffix(".owner")
    run_id = "refresh_" + "8" * 32
    running_status(status, run_id)
    source_refresh_api.create_owner(owner, run_id)
    started = tmp_path / "started"
    finished = tmp_path / "finished"
    harness = tmp_path / "hard_exit.py"
    harness.write_text(
        "import os, pathlib, subprocess, sys\n"
        "from databox import source_refresh_api as api\n"
        "owner, run_id, started, finished = sys.argv[1:]\n"
        "child=(f\"import pathlib,time; pathlib.Path({started!r}).write_text('started'); \"\n"
        "       f\"time.sleep(30); pathlib.Path({finished!r}).write_text('finished')\")\n"
        "command=[sys.executable,'-m','databox.source_refresh_gate','--run-id',run_id,'--',"
        "         sys.executable,'-c',child]\n"
        "gate=subprocess.Popen(command,stdin=subprocess.PIPE,start_new_session=True)\n"
        "api.write_owner(pathlib.Path(owner),api.owner_value(run_id,pid=os.getpid(),child_pid=gate.pid))\n"
        "gate.stdin.write(f'GO {run_id}\\n'.encode()); gate.stdin.flush(); gate.stdin.close()\n"
        "os._exit(0)\n",
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, str(harness), str(owner), run_id, str(started), str(finished)],
        check=True,
    )
    for _ in range(50):
        if started.exists():
            break
        time.sleep(0.02)
    assert started.exists()
    value = source_refresh_api.read_owner(owner)
    assert value is not None and isinstance(value["child_pid"], int)
    value["heartbeat_at"] = "2026-01-01T00:00:00+00:00"
    source_refresh_api.write_owner(owner, value)
    response = app(status).get("/api/source-refresh")
    assert response.json()["state"] == "failed"
    assert not owner.exists()
    time.sleep(0.1)
    assert not finished.exists()

    FakeProcess.calls.clear()
    monkeypatch.setattr(source_refresh_api.subprocess, "Popen", FakeProcess)
    assert app(status).post("/api/source-refresh", json={"confirm": True}).status_code == 202


def test_atomic_status_and_owner_validation_are_bounded(tmp_path: Path) -> None:
    path = tmp_path / "status.json"
    path.write_bytes(b"x" * (source_refresh_api.MAX_STATUS_BYTES + 1))
    assert app(path).get("/api/source-refresh").json()["state"] == "idle"
    owner = path.with_suffix(".owner")
    owner.write_bytes(b"x" * (source_refresh_api.MAX_OWNER_BYTES + 1))
    assert app(path).post("/api/source-refresh", json={"confirm": True}).status_code == 409
