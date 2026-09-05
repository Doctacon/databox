#!/usr/bin/env python3
"""Fail-closed readiness gate for the Polaris PostgreSQL catalog."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

_READY_MARKER = Path("/var/run/postgresql/.databox-catalog-backup-ready")
_PGBACKREST = "/usr/local/bin/run-pgbackrest"
Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class ReadinessError(RuntimeError):
    """The catalog backup cannot currently protect Polaris."""


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def _require_configuration() -> None:
    required = (
        "PGBACKREST_REPO1_CIPHER_PASS",
        "PGBACKREST_REPO1_S3_KEY",
        "PGBACKREST_REPO1_S3_KEY_SECRET",
        "PGBACKREST_REPO1_S3_TOKEN",
        "PGBACKREST_REPO1_S3_BUCKET",
        "PGBACKREST_REPO1_S3_REGION",
        "PGBACKREST_REPO1_S3_ENDPOINT",
    )
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise ReadinessError("missing catalog backup settings: " + ", ".join(missing))


def _has_valid_backup(info_text: str) -> bool:
    try:
        payload: Any = json.loads(info_text)
    except json.JSONDecodeError as exc:
        raise ReadinessError("pgBackRest returned invalid repository information") from exc
    if not isinstance(payload, list):
        raise ReadinessError("pgBackRest repository information has an unexpected shape")
    for stanza in payload:
        if not isinstance(stanza, dict) or stanza.get("name") != "polaris":
            continue
        status = stanza.get("status")
        if not isinstance(status, dict) or status.get("code") != 0:
            continue
        backups = stanza.get("backup", [])
        if isinstance(backups, list) and any(
            isinstance(backup, dict) and backup.get("error") is not True for backup in backups
        ):
            return True
    return False


def ensure_catalog_backup_ready(*, runner: Runner = _run, marker: Path = _READY_MARKER) -> None:
    """Verify WAL archival and ensure one physical backup before marking ready."""
    if marker.is_file():
        return
    _require_configuration()
    try:
        runner(("pg_isready", "-U", "polaris", "-d", "polaris"))
        runner((_PGBACKREST, "--stanza=polaris", "stanza-create"))
        runner((_PGBACKREST, "--stanza=polaris", "check"))
        info = runner((_PGBACKREST, "--stanza=polaris", "--output=json", "info"))
        if not _has_valid_backup(info.stdout):
            runner((_PGBACKREST, "--stanza=polaris", "--type=full", "backup"))
            info = runner((_PGBACKREST, "--stanza=polaris", "--output=json", "info"))
            if not _has_valid_backup(info.stdout):
                raise ReadinessError("initial catalog backup was not visible after completion")
    except subprocess.CalledProcessError as exc:
        command = Path(str(exc.cmd[0])).name if isinstance(exc.cmd, list | tuple) else "command"
        raise ReadinessError(f"catalog backup readiness command failed: {command}") from exc
    marker.touch(mode=0o600)


def main() -> int:
    try:
        ensure_catalog_backup_ready()
    except (OSError, ReadinessError, ValueError) as exc:
        print(f"catalog backup is not ready: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
