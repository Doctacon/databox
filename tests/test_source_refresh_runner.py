from __future__ import annotations

from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import pytest
from databox import source_refresh_api, source_refresh_runner
from databox.orchestration.parallel_refresh import (
    ParallelRefreshError,
    SourceRunResult,
    WarehouseInspection,
    execute_parallel_refresh,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeProcess:
    pid = 424242

    def __init__(self, output: bytes, return_code: int) -> None:
        self.stdin = BytesIO()
        self.stdout = BytesIO(output)
        self.return_code = return_code

    def wait(self, timeout: float | None = None) -> int:
        _ = timeout
        return self.return_code

    def terminate(self) -> None:
        self.return_code = -15

    def kill(self) -> None:
        self.return_code = -9


def initial(path: Path, owner: Path, run_id: str, log_name: str) -> None:
    value = source_refresh_api.idle_status()
    value.update(
        run_id=run_id,
        state="running_sources",
        started_at="2026-07-12T12:00:00+00:00",
        safe_message="Refreshing routine sources",
        log_name="rufous-source-refresh.log",
    )
    source_refresh_api.write_status(path, value)
    source_refresh_api.create_owner(owner, run_id)


def markers(failed: str | None = None) -> bytes:
    lines: list[str] = []
    for source in source_refresh_runner.ROUTINE_SOURCES:
        lines.append(f"SOURCE_START source={source} at=2026-07-12T12:00:00Z")
        code = 1 if source == failed else 0
        lines.append(
            f"SOURCE_END source={source} at=2026-07-12T12:00:01Z "
            f"status={code} process_seconds=1 ingest_seconds=1"
        )
    if failed is None:
        lines.append("PHASE_START phase=sqlmesh")
    lines.extend(
        [
            "provider payload password=hunter2 token=secret",
            "raw exception https://private.example/path?credential=secret",
            "x" * 20_000,
        ]
    )
    return ("\n".join(lines) + "\n").encode()


def test_runner_pins_exact_scope_recovers_success_and_sanitizes_log(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    owner = tmp_path / "status.owner"
    log = tmp_path / "refresh.log"
    run_id = "refresh_" + "a" * 32
    initial(status, owner, run_id, log.name)
    calls: list[tuple[list[str], dict[str, object]]] = []

    def popen(command: list[str], **options: object):
        calls.append((command, options))
        return FakeProcess(markers(), 0)

    assert (
        source_refresh_runner.run_refresh(
            status_path=status,
            owner_path=owner,
            log_path=log,
            run_id=run_id,
            sources=source_refresh_runner.ROUTINE_SOURCES,
            popen=popen,
        )
        == 0
    )
    result = source_refresh_api.read_status(status)
    assert result["state"] == "succeeded"
    assert all(item["status"] == "succeeded" for item in result["sources"])
    assert not owner.exists()
    command, options = calls[0]
    assert command[:5] == [
        str(source_refresh_runner.PROJECT_ROOT / ".venv" / "bin" / "python"),
        "-m",
        "databox.source_refresh_gate",
        "--run-id",
        run_id,
    ]
    separator = command.index("--")
    assert command[separator + 1 : separator + 4] == [
        str(source_refresh_runner.PROJECT_ROOT / ".venv" / "bin" / "python"),
        str(source_refresh_runner.PROJECT_ROOT / "scripts" / "load_dlt_quack.py"),
        "--database",
    ]
    assert [
        command[index + 1] for index, item in enumerate(command[:-1]) if item == "--source"
    ] == list(source_refresh_runner.ROUTINE_SOURCES)
    assert options["stdin"] == source_refresh_runner.subprocess.PIPE
    assert options["stdout"] == source_refresh_runner.subprocess.PIPE
    assert options["stderr"] == source_refresh_runner.subprocess.STDOUT
    assert options["start_new_session"] is True
    safe_log = log.read_text()
    assert "PHASE sqlmesh" in safe_log
    assert "RUN_END status=ok" in safe_log
    assert "hunter2" not in safe_log
    assert "private.example" not in safe_log
    assert "credential" not in safe_log
    assert log.stat().st_size <= source_refresh_runner.MAX_SAFE_LOG_BYTES


def test_source_failure_is_attributed_and_never_enters_sqlmesh(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    owner = tmp_path / "status.owner"
    log = tmp_path / "refresh.log"
    run_id = "refresh_" + "b" * 32
    initial(status, owner, run_id, log.name)

    assert (
        source_refresh_runner.run_refresh(
            status_path=status,
            owner_path=owner,
            log_path=log,
            run_id=run_id,
            sources=source_refresh_runner.ROUTINE_SOURCES,
            popen=lambda *args, **kwargs: FakeProcess(markers("gbif"), 1),
        )
        == 1
    )
    result = source_refresh_api.read_status(status)
    assert result["state"] == "failed"
    assert result["safe_message"] == "Source gbif failed; inspect the local log"
    by_name = {item["name"]: item["status"] for item in result["sources"]}
    assert by_name["gbif"] == "failed"
    assert "PHASE sqlmesh" not in log.read_text()


def test_owner_publication_failure_starts_no_warehouse_process(tmp_path: Path, monkeypatch) -> None:
    status = tmp_path / "status.json"
    owner = tmp_path / "status.owner"
    run_id = "refresh_" + "c" * 32
    initial(status, owner, run_id, "refresh.log")
    called = False

    def fail_write(*args, **kwargs):
        raise OSError("cannot publish")

    def popen(*args, **kwargs):
        nonlocal called
        called = True
        return FakeProcess(b"", 0)

    monkeypatch.setattr(source_refresh_runner, "write_owner", fail_write)
    assert (
        source_refresh_runner.run_refresh(
            status_path=status,
            owner_path=owner,
            log_path=tmp_path / "refresh.log",
            run_id=run_id,
            sources=source_refresh_runner.ROUTINE_SOURCES,
            popen=popen,
        )
        == 1
    )
    assert not called
    assert not owner.exists()
    assert source_refresh_api.read_status(status)["state"] == "failed"


def test_status_failure_stops_orchestration_group_before_releasing_owner(
    tmp_path: Path, monkeypatch
) -> None:
    status = tmp_path / "status.json"
    owner = tmp_path / "status.owner"
    run_id = "refresh_" + "9" * 32
    initial(status, owner, run_id, "refresh.log")
    signals: list[int] = []

    class RunningProcess(FakeProcess):
        pid = 424242

        def wait(self, timeout: float | None = None) -> int:
            _ = timeout
            return self.return_code

        def terminate(self) -> None:
            raise AssertionError("process-group termination should be used")

        def kill(self) -> None:
            raise AssertionError("process-group kill should not be needed")

    monkeypatch.setattr(
        source_refresh_runner,
        "_source_update",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("status changed")),
    )
    monkeypatch.setattr(
        source_refresh_runner.os,
        "killpg",
        lambda pid, value: signals.append(value) if pid == RunningProcess.pid else None,
    )
    monkeypatch.setattr(source_refresh_runner, "process_group_exists", lambda _: False)
    assert (
        source_refresh_runner.run_refresh(
            status_path=status,
            owner_path=owner,
            log_path=tmp_path / "refresh.log",
            run_id=run_id,
            sources=source_refresh_runner.ROUTINE_SOURCES,
            popen=lambda *args, **kwargs: RunningProcess(markers(), 0),
        )
        == 1
    )
    assert signals == [source_refresh_runner.signal.SIGTERM]
    assert not owner.exists()
    assert source_refresh_api.read_status(status)["state"] == "failed"


def test_unexpected_post_launch_error_cleans_group_and_keeps_owner_on_uncertainty(
    tmp_path: Path, monkeypatch
) -> None:
    status = tmp_path / "status.json"
    owner = tmp_path / "status.owner"
    run_id = "refresh_" + "5" * 32
    initial(status, owner, run_id, "refresh.log")
    stopped: list[int] = []
    monkeypatch.setattr(
        source_refresh_runner,
        "_source_update",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("invalid status")),
    )
    monkeypatch.setattr(
        source_refresh_runner,
        "_stop_process",
        lambda process: stopped.append(process.pid) or False,
    )

    with pytest.raises(ValueError, match="invalid status"):
        source_refresh_runner.run_refresh(
            status_path=status,
            owner_path=owner,
            log_path=tmp_path / "refresh.log",
            run_id=run_id,
            sources=source_refresh_runner.ROUTINE_SOURCES,
            popen=lambda *args, **kwargs: FakeProcess(markers(), 0),
        )

    assert stopped == [FakeProcess.pid]
    assert owner.exists()
    assert source_refresh_api.read_status(status)["state"] == "running_sources"


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(7)])
def test_interrupts_cleanup_group_and_propagate(
    tmp_path: Path, monkeypatch, interrupt: BaseException
) -> None:
    status = tmp_path / "status.json"
    owner = tmp_path / "status.owner"
    run_id = "refresh_" + ("3" if isinstance(interrupt, KeyboardInterrupt) else "4") * 32
    initial(status, owner, run_id, "refresh.log")
    stopped: list[int] = []
    monkeypatch.setattr(
        source_refresh_runner,
        "_source_update",
        lambda *args, **kwargs: (_ for _ in ()).throw(interrupt),
    )
    monkeypatch.setattr(
        source_refresh_runner,
        "_stop_process",
        lambda process: stopped.append(process.pid) or True,
    )

    with pytest.raises(type(interrupt)):
        source_refresh_runner.run_refresh(
            status_path=status,
            owner_path=owner,
            log_path=tmp_path / "refresh.log",
            run_id=run_id,
            sources=source_refresh_runner.ROUTINE_SOURCES,
            popen=lambda *args, **kwargs: FakeProcess(markers(), 0),
        )

    assert stopped == [FakeProcess.pid]
    assert not owner.exists()


def test_status_failure_keeps_owner_when_group_exit_is_uncertain(
    tmp_path: Path, monkeypatch
) -> None:
    status = tmp_path / "status.json"
    owner = tmp_path / "status.owner"
    run_id = "refresh_" + "8" * 32
    initial(status, owner, run_id, "refresh.log")
    monkeypatch.setattr(
        source_refresh_runner,
        "_source_update",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("status changed")),
    )
    monkeypatch.setattr(source_refresh_runner, "_stop_process", lambda _: False)
    assert (
        source_refresh_runner.run_refresh(
            status_path=status,
            owner_path=owner,
            log_path=tmp_path / "refresh.log",
            run_id=run_id,
            sources=source_refresh_runner.ROUTINE_SOURCES,
            popen=lambda *args, **kwargs: FakeProcess(markers(), 0),
        )
        == 1
    )
    assert owner.exists()
    assert source_refresh_api.read_status(status)["state"] == "failed"


@pytest.mark.parametrize("return_code", [0, 1])
def test_normal_gate_exit_keeps_owner_when_group_absence_is_unproven(
    tmp_path: Path,
    monkeypatch,
    return_code: int,
) -> None:
    status = tmp_path / "status.json"
    owner = tmp_path / "status.owner"
    run_id = "refresh_" + ("6" if return_code == 0 else "7") * 32
    initial(status, owner, run_id, "refresh.log")
    stopped: list[int] = []
    monkeypatch.setattr(source_refresh_runner, "process_group_exists", lambda _: True)
    monkeypatch.setattr(
        source_refresh_runner,
        "_stop_process",
        lambda process: stopped.append(process.pid) or False,
    )

    result = source_refresh_runner.run_refresh(
        status_path=status,
        owner_path=owner,
        log_path=tmp_path / "refresh.log",
        run_id=run_id,
        sources=source_refresh_runner.ROUTINE_SOURCES,
        popen=lambda *args, **kwargs: FakeProcess(markers(), return_code),
    )

    assert result == (0 if return_code == 0 else 1)
    assert stopped == [FakeProcess.pid]
    assert owner.exists()
    assert source_refresh_api.read_status(status)["state"] == (
        "succeeded" if return_code == 0 else "failed"
    )


def test_runner_rejects_noncanonical_scope_without_starting(tmp_path: Path) -> None:
    called = False

    def popen(*args, **kwargs):
        nonlocal called
        called = True
        return FakeProcess(b"", 0)

    try:
        source_refresh_runner.run_refresh(
            status_path=tmp_path / "status",
            owner_path=tmp_path / "owner",
            log_path=tmp_path / "log",
            run_id="refresh_" + "d" * 32,
            sources=("ebird",),
            popen=popen,
        )
    except ValueError as error:
        assert str(error) == "refresh source scope does not match the canonical registry"
    else:
        raise AssertionError("noncanonical scope was accepted")
    assert not called


def test_connected_exact_six_api_runner_uses_real_one_quack_orchestration_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    events: list[str] = []

    class FakeServer:
        def __enter__(self) -> None:
            events.append("server-start")

        def __exit__(self, *args: Any) -> None:
            events.append("server-stop")

    def source(source: str, workdir: Path, env: dict[str, str]) -> SourceRunResult:
        _ = workdir, env
        print(f"SOURCE_START source={source} at=start", flush=True)
        print(
            f"SOURCE_END source={source} at=end status=0 process_seconds=1 ingest_seconds=1",
            flush=True,
        )
        return SourceRunResult(source, 0, 1.0, 2.0, "start", "end", "completed")

    launched: list[list[str]] = []

    class Launcher:
        def __init__(self, command: list[str], **kwargs: object) -> None:
            launched.append(command)

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(source_refresh_api.subprocess, "Popen", Launcher)
    status = tmp_path / "status.json"
    application = FastAPI()
    source_refresh_api.register_source_refresh_routes(application, status_path=status)
    response = TestClient(application, base_url="http://127.0.0.1").post(
        "/api/source-refresh", json={"confirm": True}
    )
    assert response.status_code == 202
    command = launched[0]
    run_id = command[command.index("--run-id") + 1]
    owner = Path(command[command.index("--owner") + 1])
    api_sources = tuple(
        command[index + 1] for index, item in enumerate(command[:-1]) if item == "--source"
    )

    output = StringIO()
    with redirect_stdout(output):
        execute_parallel_refresh(
            list(api_sources),
            database_path=str(tmp_path / "warehouse.duckdb"),
            source_runner=source,
            server_factory=lambda _: FakeServer(),
            dedupe_runner=lambda _: events.append("dedupe") or [],
            cleanup_runner=lambda: events.append("cleanup"),
            inspection_runner=lambda *_: events.append("inspect") or WarehouseInspection((), ()),
            transform_runner=lambda: events.append("sqlmesh"),
        )
    assert events.count("server-start") == 1
    assert events.index("server-stop") < events.index("dedupe")
    assert events.index("dedupe") < events.index("inspect") < events.index("sqlmesh")
    assert events.index("cleanup") < events.index("inspect")
    rendered = output.getvalue()
    assert rendered.count("SOURCE_START source=") == len(api_sources)
    assert rendered.index("PHASE_START phase=sqlmesh") > rendered.rindex("SOURCE_END source=")

    log = tmp_path / "refresh.log"
    assert (
        source_refresh_runner.run_refresh(
            status_path=status,
            owner_path=owner,
            log_path=log,
            run_id=run_id,
            sources=api_sources,
            popen=lambda *args, **kwargs: FakeProcess(rendered.encode(), 0),
        )
        == 0
    )
    assert source_refresh_api.read_status(status)["state"] == "succeeded"
    assert "PHASE sqlmesh" in log.read_text()


def test_connected_exact_six_source_failure_suppresses_sqlmesh(tmp_path: Path, monkeypatch) -> None:
    events: list[str] = []

    class FakeServer:
        def __enter__(self) -> None:
            events.append("server-start")

        def __exit__(self, *args: Any) -> None:
            events.append("server-stop")

    def source(source: str, workdir: Path, env: dict[str, str]) -> SourceRunResult:
        _ = workdir, env
        failed = source == "gbif"
        print(f"SOURCE_START source={source} at=start", flush=True)
        print(
            f"SOURCE_END source={source} at=end status={1 if failed else 0} "
            "process_seconds=1 ingest_seconds=1",
            flush=True,
        )
        return SourceRunResult(
            source,
            1 if failed else 0,
            1.0,
            2.0,
            "start",
            "end",
            "failed" if failed else "completed",
        )

    launched: list[list[str]] = []

    class Launcher:
        def __init__(self, command: list[str], **kwargs: object) -> None:
            launched.append(command)

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(source_refresh_api.subprocess, "Popen", Launcher)
    status = tmp_path / "status.json"
    application = FastAPI()
    source_refresh_api.register_source_refresh_routes(application, status_path=status)
    response = TestClient(application, base_url="http://127.0.0.1").post(
        "/api/source-refresh", json={"confirm": True}
    )
    assert response.status_code == 202
    command = launched[0]
    run_id = command[command.index("--run-id") + 1]
    owner = Path(command[command.index("--owner") + 1])
    api_sources = tuple(
        command[index + 1] for index, item in enumerate(command[:-1]) if item == "--source"
    )

    output = StringIO()
    try:
        with redirect_stdout(output):
            execute_parallel_refresh(
                list(api_sources),
                database_path=str(tmp_path / "warehouse.duckdb"),
                source_runner=source,
                server_factory=lambda _: FakeServer(),
                dedupe_runner=lambda _: events.append("dedupe") or [],
                cleanup_runner=lambda: events.append("cleanup"),
                inspection_runner=lambda *_: (
                    events.append("inspect") or WarehouseInspection((), ())
                ),
                transform_runner=lambda: events.append("sqlmesh"),
            )
    except ParallelRefreshError as error:
        assert "gbif" in str(error)
    else:
        raise AssertionError("failed exact-six orchestration unexpectedly succeeded")
    assert events.count("server-start") == 1
    assert events.index("server-stop") < events.index("dedupe")
    assert events.index("dedupe") < events.index("cleanup")
    assert "inspect" not in events
    assert "sqlmesh" not in events
    assert "PHASE_START phase=sqlmesh" not in output.getvalue()

    log = tmp_path / "refresh.log"
    assert (
        source_refresh_runner.run_refresh(
            status_path=status,
            owner_path=owner,
            log_path=log,
            run_id=run_id,
            sources=api_sources,
            popen=lambda *args, **kwargs: FakeProcess(output.getvalue().encode(), 1),
        )
        == 1
    )
    assert (
        source_refresh_api.read_status(status)["safe_message"]
        == "Source gbif failed; inspect the local log"
    )
    assert "PHASE sqlmesh" not in log.read_text()
