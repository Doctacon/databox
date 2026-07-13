"""Durable, bounded status runner for the local routine-source refresh."""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, cast

from databox.config.settings import PROJECT_ROOT, settings
from databox.config.sources import SOURCES
from databox.source_refresh_api import (
    owner_is_fresh,
    owner_value,
    process_group_exists,
    read_owner,
    read_status,
    release_owner,
    write_owner,
    write_status,
)

ROUTINE_SOURCES = tuple(source.name for source in SOURCES if source.parallel_refresh)
MAX_CAPTURE_BUFFER = 8_192
MAX_SAFE_LOG_BYTES = 64_000
HEARTBEAT_SECONDS = 2
_START = re.compile(rb"^SOURCE_START source=([a-z0-9_]+) ")
_END = re.compile(rb"^SOURCE_END source=([a-z0-9_]+) .* status=([0-9]+) ")
_SQLMESH = re.compile(rb"^PHASE_START phase=sqlmesh$")


def _append_safe(log_path: Path, message: str) -> None:
    encoded = (message + "\n").encode("utf-8")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    current_size = log_path.stat().st_size if log_path.exists() else 0
    if current_size + len(encoded) <= MAX_SAFE_LOG_BYTES:
        with log_path.open("ab") as stream:
            stream.write(encoded)


def _safe_lines(stream: IO[bytes]) -> Iterator[bytes]:
    buffer = b""
    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            yield line[:MAX_CAPTURE_BUFFER]
        if len(buffer) > MAX_CAPTURE_BUFFER:
            buffer = buffer[-MAX_CAPTURE_BUFFER:]
    if buffer:
        yield buffer[:MAX_CAPTURE_BUFFER]


def _update(path: Path, run_id: str, **changes: object) -> dict[str, object]:
    current = read_status(path)
    if current.get("run_id") != run_id:
        raise RuntimeError("refresh run identity changed")
    updated = {**current, **changes}
    write_status(path, updated)
    return updated


def _source_rows(current: dict[str, object]) -> list[dict[str, str]]:
    return cast(list[dict[str, str]], current["sources"])


def _source_update(path: Path, run_id: str, source: str, source_status: str) -> None:
    current = read_status(path)
    sources = [
        {**item, "status": source_status} if item["name"] == source else item
        for item in _source_rows(current)
    ]
    _update(path, run_id, sources=sources)


def _claim_owner(path: Path, run_id: str) -> None:
    current = read_owner(path)
    if (
        current is None
        or current.get("run_id") != run_id
        or current.get("pid") is not None
        or not owner_is_fresh(current)
    ):
        raise RuntimeError("refresh ownership is unavailable")
    write_owner(path, owner_value(run_id, pid=os.getpid()))


def _publish_child(path: Path, run_id: str, child_pid: int) -> None:
    current = read_owner(path)
    if current is None or current.get("run_id") != run_id or current.get("pid") != os.getpid():
        raise RuntimeError("refresh ownership changed before child publication")
    write_owner(path, owner_value(run_id, pid=os.getpid(), child_pid=child_pid))


def _heartbeat(path: Path, run_id: str, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_SECONDS):
        current = read_owner(path)
        if current is None or current.get("run_id") != run_id or current.get("pid") != os.getpid():
            return
        try:
            write_owner(
                path,
                owner_value(
                    run_id,
                    pid=os.getpid(),
                    child_pid=cast(int | None, current.get("child_pid")),
                ),
            )
        except OSError:
            return


def _wait_for_group_exit(process_group_id: int) -> bool:
    for _ in range(20):
        state = process_group_exists(process_group_id)
        if state is False:
            return True
        if state is None:
            return False
        threading.Event().wait(0.05)
    return False


def _stop_process(process: subprocess.Popen[bytes]) -> bool:
    """Stop and prove the whole isolated group gone before ownership release."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return process_group_exists(process.pid) is False
    except OSError:
        return False
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    if _wait_for_group_exit(process.pid):
        return True
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return process_group_exists(process.pid) is False
    except OSError:
        return False
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return _wait_for_group_exit(process.pid)


def run_refresh(
    *,
    status_path: Path,
    owner_path: Path,
    log_path: Path,
    run_id: str,
    sources: tuple[str, ...],
    popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
) -> int:
    if sources != ROUTINE_SOURCES:
        raise ValueError("refresh source scope does not match the canonical registry")
    if read_status(status_path).get("run_id") != run_id:
        raise RuntimeError("refresh status identity changed")
    try:
        _claim_owner(owner_path, run_id)
    except (OSError, RuntimeError, ValueError):
        try:
            _update(
                status_path,
                run_id,
                state="failed",
                finished_at=datetime.now(UTC).isoformat(),
                safe_message="Routine source refresh could not start",
            )
        finally:
            release_owner(owner_path, run_id)
        return 1

    orchestration_command = [
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        str(PROJECT_ROOT / "scripts" / "load_dlt_quack.py"),
        "--database",
        str(settings.database_path),
    ]
    for source in sources:
        orchestration_command.extend(("--source", source))
    command = [
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        "-m",
        "databox.source_refresh_gate",
        "--run-id",
        run_id,
        "--",
        *orchestration_command,
    ]

    stop = threading.Event()
    heartbeat: threading.Thread | None = None
    _append_safe(log_path, f"RUN_START run_id={run_id}")
    failed_source: str | None = None
    saw_sqlmesh = False
    safe_to_release = False
    process: subprocess.Popen[bytes] | None = None
    try:
        try:
            process = popen(
                command,
                cwd=PROJECT_ROOT,
                env=os.environ.copy(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            if process.stdin is None or process.stdout is None:
                raise OSError("refresh gate pipes unavailable")
            _publish_child(owner_path, run_id, process.pid)
            heartbeat = threading.Thread(
                target=_heartbeat, args=(owner_path, run_id, stop), daemon=True
            )
            heartbeat.start()
            process.stdin.write(f"GO {run_id}\n".encode("ascii"))
            process.stdin.flush()
            process.stdin.close()
            for line in _safe_lines(process.stdout):
                start = _START.match(line)
                if start:
                    source = start.group(1).decode("ascii")
                    if source in sources:
                        _source_update(status_path, run_id, source, "running")
                        _append_safe(log_path, f"SOURCE_START source={source}")
                    continue
                end = _END.match(line)
                if end:
                    source = end.group(1).decode("ascii")
                    if source not in sources:
                        continue
                    ok = int(end.group(2)) == 0
                    _source_update(status_path, run_id, source, "succeeded" if ok else "failed")
                    _append_safe(
                        log_path,
                        f"SOURCE_END source={source} status={'ok' if ok else 'failed'}",
                    )
                    if not ok and failed_source is None:
                        failed_source = source
                    continue
                if _SQLMESH.match(line):
                    current = read_status(status_path)
                    if not all(item["status"] == "succeeded" for item in _source_rows(current)):
                        raise RuntimeError("SQLMesh phase began before every source succeeded")
                    saw_sqlmesh = True
                    _update(
                        status_path,
                        run_id,
                        state="running_sqlmesh",
                        safe_message="Routine sources complete; materializing SQLMesh models",
                    )
                    _append_safe(log_path, "PHASE sqlmesh")
            return_code = process.wait()
            safe_to_release = process_group_exists(process.pid) is False
            if not safe_to_release:
                safe_to_release = _stop_process(process)
        except (OSError, RuntimeError):
            safe_to_release = process is None or _stop_process(process)
            return_code = 1

        current = read_status(status_path)
        all_succeeded = all(item["status"] == "succeeded" for item in _source_rows(current))
        succeeded = return_code == 0 and all_succeeded and saw_sqlmesh
        if succeeded:
            message = "Routine source refresh completed"
        elif failed_source:
            message = f"Source {failed_source} failed; inspect the local log"
        else:
            message = "Routine source refresh failed safely; inspect the local log"
        _update(
            status_path,
            run_id,
            state="succeeded" if succeeded else "failed",
            finished_at=datetime.now(UTC).isoformat(),
            safe_message=message,
        )
        _append_safe(log_path, f"RUN_END status={'ok' if succeeded else 'failed'}")
        return 0 if succeeded else 1
    except BaseException:
        # Ownership defaults fail closed after launch. Cleanup must run even for
        # interrupts, but KeyboardInterrupt/SystemExit and unexpected failures
        # retain their normal propagation semantics.
        if process is None:
            safe_to_release = True
        elif not safe_to_release:
            safe_to_release = _stop_process(process)
        raise
    finally:
        stop.set()
        if heartbeat is not None:
            heartbeat.join(timeout=HEARTBEAT_SECONDS)
        if safe_to_release:
            release_owner(owner_path, run_id)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--owner", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source", action="append", choices=ROUTINE_SOURCES, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return run_refresh(
        status_path=args.status,
        owner_path=args.owner,
        log_path=args.log,
        run_id=args.run_id,
        sources=tuple(args.source),
    )


if __name__ == "__main__":
    raise SystemExit(main())
