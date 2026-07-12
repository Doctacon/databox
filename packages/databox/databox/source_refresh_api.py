"""Confirmed loopback-only launcher for the established full-refresh command."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from databox.config.settings import PROJECT_ROOT

ROUTINE_SOURCES = ("ebird", "gbif", "xeno_canto", "noaa", "usgs", "usgs_earthquakes")


class RefreshLaunch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirm: Literal[True]


class RefreshStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str | None
    state: Literal["idle", "running_sources", "running_sqlmesh", "succeeded", "failed"]
    sources: list[str]
    started_at: str | None
    finished_at: str | None
    safe_message: str | None
    log_name: str | None


def _write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _idle() -> dict[str, object]:
    return {
        "run_id": None,
        "state": "idle",
        "sources": list(ROUTINE_SOURCES),
        "started_at": None,
        "finished_at": None,
        "safe_message": None,
        "log_name": None,
    }


def _read(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return RefreshStatus.model_validate(value).model_dump()
    except (OSError, ValueError):
        return _idle()


def _same_origin(request: Request) -> bool:
    host = request.headers.get("host", "")
    hostname = host.split(":", 1)[0].lower()
    if hostname not in {"127.0.0.1", "localhost", "[::1]"}:
        return False
    origin = request.headers.get("origin")
    if origin is None:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme == "http" and parsed.netloc == host


def register_source_refresh_routes(app: FastAPI, *, status_path: Path | None = None) -> None:
    path = status_path or PROJECT_ROOT / ".logs" / "rufous-refresh-status.json"
    log_dir = PROJECT_ROOT / ".logs"

    def latest_log(started_at: object = None) -> Path | None:
        threshold = 0.0
        if isinstance(started_at, str):
            try:
                threshold = datetime.fromisoformat(started_at).timestamp() - 1
            except ValueError:
                return None
        matches = sorted(
            item
            for item in log_dir.glob("rufous-source-refresh-*.log")
            if item.stat().st_mtime >= threshold
        )
        return matches[-1] if matches else None

    pid_path = path.with_suffix(".pid")
    lock = asyncio.Lock()
    app.state.source_refresh_task = None

    @app.get("/api/source-refresh", response_model=RefreshStatus)
    async def source_refresh_status() -> RefreshStatus:
        current = _read(path)
        if current["state"] in {"running_sources", "running_sqlmesh"}:
            log = latest_log(current.get("started_at"))
            if current["state"] == "running_sources" and log is not None:
                try:
                    if log.read_text(encoding="utf-8", errors="replace").count(
                        "SOURCE_END source="
                    ) >= len(ROUTINE_SOURCES):
                        current = {
                            **current,
                            "state": "running_sqlmesh",
                            "safe_message": "Materializing SQLMesh models",
                            "log_name": log.name,
                        }
                        _write(path, current)
                except OSError:
                    pass
            try:
                pid = int(pid_path.read_text(encoding="ascii"))
                os.kill(pid, 0)
            except (OSError, ValueError):
                current = {
                    **current,
                    "state": "failed",
                    "finished_at": datetime.now(UTC).isoformat(),
                    "safe_message": (
                        "Source refresh process is no longer running; inspect the local log"
                    ),
                }
                _write(path, current)
                pid_path.unlink(missing_ok=True)
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
            current = _read(path)
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
            log_name = "rufous-source-refresh-*.log"
            status: dict[str, object] = {
                "run_id": run_id,
                "state": "running_sources",
                "sources": list(ROUTINE_SOURCES),
                "started_at": started,
                "finished_at": None,
                "safe_message": "Refreshing routine sources",
                "log_name": log_name,
            }
            _write(path, status)

            async def run() -> None:
                command = [
                    str(PROJECT_ROOT / "scripts" / "run-logged.sh"),
                    "rufous-source-refresh",
                    "--",
                    str(PROJECT_ROOT / ".venv" / "bin" / "python"),
                    str(PROJECT_ROOT / "scripts" / "load_dlt_quack.py"),
                ]
                environment = os.environ.copy()
                environment["DAGSTER_HOME"] = str(PROJECT_ROOT / ".dagster")
                environment["RUNTIME__DLTHUB_TELEMETRY"] = "false"
                environment["SQLMESH__DISABLE_ANONYMIZED_ANALYTICS"] = "true"
                final: dict[str, object]
                try:
                    process = subprocess.Popen(command, cwd=PROJECT_ROOT, env=environment)
                    pid_path.write_text(str(process.pid), encoding="ascii")
                    ok = await asyncio.to_thread(process.wait) == 0
                    final = {
                        **status,
                        "state": "succeeded" if ok else "failed",
                        "finished_at": datetime.now(UTC).isoformat(),
                        "safe_message": "Routine source refresh completed"
                        if ok
                        else "Routine source refresh failed; inspect the local log",
                    }
                except OSError:
                    final = {
                        **status,
                        "state": "failed",
                        "finished_at": datetime.now(UTC).isoformat(),
                        "safe_message": "Routine source refresh could not start",
                    }
                log = latest_log(status.get("started_at"))
                if log is not None:
                    final["log_name"] = log.name
                _write(path, final)
                pid_path.unlink(missing_ok=True)

            app.state.source_refresh_task = asyncio.create_task(run())
            return RefreshStatus.model_validate(status)
