"""Confirmed loopback-only launcher for the established full-refresh command."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import re
import signal
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from databox.config.settings import PROJECT_ROOT
from databox.config.sources import SOURCES

MAX_STATUS_BYTES = 16_384
MAX_OWNER_BYTES = 1_024
OWNER_STALE_SECONDS = 10
ROUTINE_SOURCES = tuple(source.name for source in SOURCES if source.parallel_refresh)


class RefreshLaunch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirm: Literal[True]


class SourceProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    status: Literal["pending", "running", "succeeded", "failed"]


class RefreshStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str | None
    state: Literal["idle", "running_sources", "running_sqlmesh", "succeeded", "failed"]
    sources: list[SourceProgress]
    started_at: str | None
    finished_at: str | None
    safe_message: str | None
    log_name: str | None

    @field_validator("run_id")
    @classmethod
    def valid_run_id(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(r"refresh_[0-9a-f]{32}", value) is None:
            raise ValueError("invalid refresh run identity")
        return value

    @field_validator("started_at", "finished_at")
    @classmethod
    def valid_timestamp(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ValueError("refresh timestamps require a timezone")
        return value

    @field_validator("safe_message")
    @classmethod
    def valid_message(cls, value: str | None) -> str | None:
        if value is not None and (not 1 <= len(value) <= 200 or any(ch in value for ch in "\r\n")):
            raise ValueError("invalid safe refresh message")
        return value

    @field_validator("log_name")
    @classmethod
    def valid_log_name(cls, value: str | None) -> str | None:
        if (
            value is not None
            and re.fullmatch(r"rufous-source-refresh(?:-refresh_[0-9a-f]{32})?\.log", value) is None
        ):
            raise ValueError("invalid refresh log name")
        return value

    @model_validator(mode="after")
    def coherent(self) -> RefreshStatus:
        if tuple(item.name for item in self.sources) != ROUTINE_SOURCES:
            raise ValueError("refresh sources do not match canonical order")
        if self.state == "idle":
            if any(
                (self.run_id, self.started_at, self.finished_at, self.safe_message, self.log_name)
            ):
                raise ValueError("idle refresh status contains run data")
            if any(item.status != "pending" for item in self.sources):
                raise ValueError("idle sources must be pending")
            return self
        if None in (self.run_id, self.started_at, self.safe_message, self.log_name):
            raise ValueError("active or terminal refresh status is incomplete")
        if self.state in {"running_sources", "running_sqlmesh"} and self.finished_at is not None:
            raise ValueError("running refresh cannot be finished")
        if self.state in {"succeeded", "failed"} and self.finished_at is None:
            raise ValueError("terminal refresh requires finish time")
        if self.state in {"running_sqlmesh", "succeeded"} and any(
            item.status != "succeeded" for item in self.sources
        ):
            raise ValueError("SQLMesh and success require all sources")
        return self


@contextmanager
def _status_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _write_status_unlocked(path: Path, value: dict[str, object]) -> None:
    validated = RefreshStatus.model_validate(value).model_dump()
    encoded = json.dumps(validated, sort_keys=True).encode("utf-8")
    if len(encoded) > MAX_STATUS_BYTES:
        raise ValueError("refresh status exceeds safe bound")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)


def write_status(path: Path, value: dict[str, object]) -> None:
    with _status_lock(path):
        _write_status_unlocked(path, value)


def fail_running_status(path: Path, run_id: str, message: str) -> dict[str, object]:
    """Atomically fail only the same still-running durable status."""
    with _status_lock(path):
        current = read_status(path)
        if current.get("run_id") == run_id and current.get("state") in {
            "running_sources",
            "running_sqlmesh",
        }:
            current = _failed(current, message)
            _write_status_unlocked(path, current)
        return current


def idle_status() -> dict[str, object]:
    return {
        "run_id": None,
        "state": "idle",
        "sources": [{"name": name, "status": "pending"} for name in ROUTINE_SOURCES],
        "started_at": None,
        "finished_at": None,
        "safe_message": None,
        "log_name": None,
    }


def read_status(path: Path) -> dict[str, object]:
    try:
        if path.stat().st_size > MAX_STATUS_BYTES:
            return idle_status()
        value = json.loads(path.read_text(encoding="utf-8"))
        return RefreshStatus.model_validate(value).model_dump()
    except (OSError, ValueError):
        return idle_status()


def owner_value(
    run_id: str, *, pid: int | None = None, child_pid: int | None = None
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "pid": pid,
        "child_pid": child_pid,
        "heartbeat_at": datetime.now(UTC).isoformat(),
    }


def _owner_bytes(value: dict[str, object]) -> bytes:
    encoded = json.dumps(value, sort_keys=True).encode("utf-8")
    if len(encoded) > MAX_OWNER_BYTES:
        raise ValueError("refresh owner exceeds safe bound")
    return encoded


def create_owner(path: Path, run_id: str) -> None:
    """Atomically reserve refresh ownership before any process is launched."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, _owner_bytes(owner_value(run_id)))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_owner(path: Path, value: dict[str, object]) -> None:
    encoded = _owner_bytes(value)
    temporary = path.with_suffix(".owner.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)


def read_owner(path: Path) -> dict[str, object] | None:
    try:
        if path.stat().st_size > MAX_OWNER_BYTES:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != {
            "run_id",
            "pid",
            "child_pid",
            "heartbeat_at",
        }:
            return None
        run_id = value["run_id"]
        pid = value["pid"]
        child_pid = value["child_pid"]
        heartbeat = value["heartbeat_at"]
        if not isinstance(run_id, str) or re.fullmatch(r"refresh_[0-9a-f]{32}", run_id) is None:
            return None
        if pid is not None and (not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0):
            return None
        if child_pid is not None and (
            not isinstance(child_pid, int) or isinstance(child_pid, bool) or child_pid <= 0
        ):
            return None
        if not isinstance(heartbeat, str):
            return None
        datetime.fromisoformat(heartbeat)
        return value
    except (OSError, ValueError):
        return None


def owner_is_fresh(value: dict[str, object]) -> bool:
    try:
        heartbeat = datetime.fromisoformat(str(value["heartbeat_at"]))
        return (datetime.now(UTC) - heartbeat).total_seconds() < OWNER_STALE_SECONDS
    except (KeyError, ValueError, TypeError):
        return False


def _owner_process_matches(value: dict[str, object]) -> bool | None:
    """Verify stale owner identity; None means verification itself was unavailable."""
    pid = value.get("pid")
    run_id = value.get("run_id")
    if not isinstance(pid, int) or not isinstance(run_id, str):
        return False
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    command = completed.stdout.strip()
    return (
        completed.returncode == 0
        and "databox.source_refresh_runner" in command
        and f"--run-id {run_id}" in command
    )


def _child_process_matches(value: dict[str, object]) -> bool | None:
    child_pid = value.get("child_pid")
    run_id = value.get("run_id")
    if not isinstance(child_pid, int) or not isinstance(run_id, str):
        return False
    try:
        completed = subprocess.run(
            ["ps", "-p", str(child_pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    command = completed.stdout.strip()
    return (
        completed.returncode == 0
        and "databox.source_refresh_gate" in command
        and f"--run-id {run_id}" in command
    )


def process_group_exists(process_group_id: int) -> bool | None:
    """Return group existence; inspection uncertainty is deliberately distinct."""
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def owner_state(value: dict[str, object]) -> Literal["active", "orphan", "stale", "unknown"]:
    if owner_is_fresh(value):
        return "active"
    runner = _owner_process_matches(value)
    if runner is None:
        return "unknown"
    if runner:
        return "active"
    child = _child_process_matches(value)
    if child is None:
        return "unknown"
    if child:
        return "orphan"
    child_pid = value.get("child_pid")
    if not isinstance(child_pid, int):
        return "stale"
    group = process_group_exists(child_pid)
    return "stale" if group is False else "unknown"


def _wait_for_group_exit(process_group_id: int) -> bool:
    for _ in range(20):
        state = process_group_exists(process_group_id)
        if state is False:
            return True
        if state is None:
            return False
        time.sleep(0.05)
    return False


def stop_orphan(value: dict[str, object]) -> bool:
    """Terminate a verified orphan group; release only after the whole group is gone."""
    if owner_state(value) != "orphan":
        return False
    child_pid = value.get("child_pid")
    if not isinstance(child_pid, int):
        return False
    try:
        os.killpg(child_pid, signal.SIGTERM)
    except ProcessLookupError:
        return process_group_exists(child_pid) is False
    except OSError:
        return False
    if _wait_for_group_exit(child_pid):
        return True
    try:
        os.killpg(child_pid, signal.SIGKILL)
    except ProcessLookupError:
        return process_group_exists(child_pid) is False
    except OSError:
        return False
    return _wait_for_group_exit(child_pid)


def release_owner(path: Path, run_id: str) -> None:
    current = read_owner(path)
    if current is not None and current.get("run_id") == run_id:
        path.unlink(missing_ok=True)


def _same_origin(request: Request) -> bool:
    host = request.headers.get("host", "")
    parsed_host = urlsplit(f"//{host}")
    if parsed_host.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return False
    origin = request.headers.get("origin")
    if origin is None:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme == "http" and parsed.netloc == host


def _failed(current: dict[str, object], message: str) -> dict[str, object]:
    return {
        **current,
        "state": "failed",
        "finished_at": datetime.now(UTC).isoformat(),
        "safe_message": message,
    }


def register_source_refresh_routes(app: FastAPI, *, status_path: Path | None = None) -> None:
    path = status_path or PROJECT_ROOT / ".logs" / "rufous-refresh-status.json"
    owner_path = path.with_suffix(".owner")
    lock = asyncio.Lock()
    app.state.source_refresh_task = None

    @app.get("/api/source-refresh", response_model=RefreshStatus)
    async def source_refresh_status() -> RefreshStatus:
        current = read_status(path)
        owner = read_owner(owner_path)
        if current["state"] in {"running_sources", "running_sqlmesh"}:
            same_owner = owner is not None and owner.get("run_id") == current.get("run_id")
            state = (
                owner_state(owner)
                if same_owner and owner is not None
                else ("stale" if owner is None else "unknown")
            )
            safe_to_release = state == "stale" or (
                state == "orphan" and owner is not None and stop_orphan(owner)
            )
            if safe_to_release:
                current = fail_running_status(
                    path,
                    str(current["run_id"]),
                    "Source refresh process stopped unexpectedly; inspect the local log",
                )
                if owner is not None:
                    release_owner(owner_path, str(owner["run_id"]))
        return RefreshStatus.model_validate(current)

    @app.post("/api/source-refresh", response_model=RefreshStatus, status_code=202)
    async def launch_source_refresh(
        payload: RefreshLaunch, request: Request
    ) -> RefreshStatus | JSONResponse:
        if not _same_origin(request):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "forbidden",
                        "message": "Refresh requires same-origin loopback access",
                    }
                },
            )
        async with lock:
            current = read_status(path)
            owner_exists = owner_path.exists()
            owner = read_owner(owner_path)
            state = owner_state(owner) if owner is not None else "unknown"
            if owner_exists and state == "orphan":
                if owner is None or not stop_orphan(owner):
                    state = "unknown"
                else:
                    state = "stale"
            if owner_exists and (owner is None or state != "stale"):
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": {
                            "code": "refresh_busy",
                            "message": "A source refresh is already running",
                        }
                    },
                )
            if owner is not None:
                current = fail_running_status(
                    path,
                    str(owner["run_id"]),
                    "Source refresh process stopped unexpectedly; inspect the local log",
                )
                release_owner(owner_path, str(owner["run_id"]))
            if current["state"] in {"running_sources", "running_sqlmesh"}:
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": {
                            "code": "refresh_busy",
                            "message": "A source refresh is already running",
                        }
                    },
                )
            run_id = "refresh_" + uuid.uuid4().hex
            started = datetime.now(UTC).isoformat()
            log_name = f"rufous-source-refresh-{run_id}.log"
            status: dict[str, object] = {
                "run_id": run_id,
                "state": "running_sources",
                "sources": [{"name": name, "status": "pending"} for name in ROUTINE_SOURCES],
                "started_at": started,
                "finished_at": None,
                "safe_message": "Refreshing routine sources",
                "log_name": log_name,
            }
            try:
                create_owner(owner_path, run_id)
                write_status(path, status)
            except (OSError, ValueError):
                release_owner(owner_path, run_id)
                failed = _failed(status, "Routine source refresh could not start")
                write_status(path, failed)
                return RefreshStatus.model_validate(failed)
            command = [
                str(PROJECT_ROOT / ".venv" / "bin" / "python"),
                "-m",
                "databox.source_refresh_runner",
                "--status",
                str(path),
                "--owner",
                str(owner_path),
                "--log",
                str(PROJECT_ROOT / ".logs" / log_name),
                "--run-id",
                run_id,
            ]
            for source in ROUTINE_SOURCES:
                command.extend(("--source", source))
            environment = os.environ.copy()
            environment["DAGSTER_HOME"] = str(PROJECT_ROOT / ".dagster")
            environment["RUNTIME__DLTHUB_TELEMETRY"] = "false"
            environment["SQLMESH__DISABLE_ANONYMIZED_ANALYTICS"] = "true"
            try:
                process = subprocess.Popen(command, cwd=PROJECT_ROOT, env=environment)
            except OSError:
                release_owner(owner_path, run_id)
                failed = _failed(status, "Routine source refresh could not start")
                write_status(path, failed)
                return RefreshStatus.model_validate(failed)

            async def reap() -> None:
                await asyncio.to_thread(process.wait)

            app.state.source_refresh_task = asyncio.create_task(reap())
            return RefreshStatus.model_validate(status)
