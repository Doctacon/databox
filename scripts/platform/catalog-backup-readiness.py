#!/usr/bin/env python3
"""Fail-closed readiness gate for the Polaris PostgreSQL catalog."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

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


class Backup(NamedTuple):
    label: str
    backup_type: str
    stopped_at: datetime


def _parse_backups(info_text: str) -> list[Backup]:
    try:
        payload: Any = json.loads(info_text)
    except json.JSONDecodeError as exc:
        raise ReadinessError("pgBackRest returned invalid repository information") from exc
    if not isinstance(payload, list):
        raise ReadinessError("pgBackRest repository information has an unexpected shape")
    stanzas = [
        stanza for stanza in payload if isinstance(stanza, dict) and stanza.get("name") == "polaris"
    ]
    if len(stanzas) != 1:
        raise ReadinessError("pgBackRest repository information is missing the polaris stanza")
    stanza = stanzas[0]
    status = stanza.get("status")
    status_code = status.get("code") if isinstance(status, dict) else None
    if (
        not isinstance(status_code, int)
        or isinstance(status_code, bool)
        or status_code not in {0, 2}
    ):
        raise ReadinessError("pgBackRest reports the polaris stanza as unhealthy")
    raw_backups = stanza.get("backup")
    if not isinstance(raw_backups, list):
        raise ReadinessError("pgBackRest backup information has an unexpected shape")

    backups: list[Backup] = []
    for raw in raw_backups:
        if not isinstance(raw, dict):
            raise ReadinessError("pgBackRest backup entry has an unexpected shape")
        error = raw.get("error", False)
        if not isinstance(error, bool):
            raise ReadinessError("pgBackRest backup entry has an invalid error status")
        if error:
            continue
        label = raw.get("label")
        backup_type = raw.get("type")
        timestamp = raw.get("timestamp")
        stopped = timestamp.get("stop") if isinstance(timestamp, dict) else None
        if (
            not isinstance(label, str)
            or not label
            or backup_type not in {"full", "diff", "incr"}
            or not isinstance(stopped, int)
            or isinstance(stopped, bool)
            or stopped < 0
        ):
            raise ReadinessError("pgBackRest backup entry has invalid label, type, or timestamp")
        try:
            stopped_at = datetime.fromtimestamp(stopped, UTC)
        except (OSError, OverflowError, ValueError) as exc:
            raise ReadinessError("pgBackRest backup entry has an invalid timestamp") from exc
        backups.append(Backup(label, backup_type, stopped_at))
    if status_code == 2 and backups:
        raise ReadinessError("pgBackRest repository status contradicts its backup entries")
    return backups


def _required_backup_type(backups: Sequence[Backup], now: datetime) -> str | None:
    newest_full = max(
        (backup.stopped_at for backup in backups if backup.backup_type == "full"), default=None
    )
    if newest_full is None or now - newest_full >= timedelta(days=7):
        return "full"
    newest = max((backup.stopped_at for backup in backups), default=None)
    if newest is None or now - newest >= timedelta(days=1):
        return "diff"
    return None


def ensure_catalog_backup_ready(*, runner: Runner = _run, now: datetime | None = None) -> None:
    """Verify WAL archival and apply the startup-driven physical-backup cadence."""
    _require_configuration()
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ReadinessError("backup cadence time must include a timezone")
    now = now.astimezone(UTC)
    try:
        runner(("pg_isready", "-U", "polaris", "-d", "polaris"))
        runner((_PGBACKREST, "--stanza=polaris", "stanza-create"))
        runner((_PGBACKREST, "--stanza=polaris", "check"))
        info = runner((_PGBACKREST, "--stanza=polaris", "--output=json", "info"))
        backups = _parse_backups(info.stdout)
        backup_type = _required_backup_type(backups, now)
        if backup_type is not None:
            existing_labels = {backup.label for backup in backups}
            runner((_PGBACKREST, "--stanza=polaris", f"--type={backup_type}", "backup"))
            fresh_info = runner((_PGBACKREST, "--stanza=polaris", "--output=json", "info"))
            fresh_backups = _parse_backups(fresh_info.stdout)
            if not any(
                backup.backup_type == backup_type and backup.label not in existing_labels
                for backup in fresh_backups
            ):
                raise ReadinessError(
                    f"new successful {backup_type} catalog backup was not visible after completion"
                )
    except subprocess.CalledProcessError as exc:
        command = Path(str(exc.cmd[0])).name if isinstance(exc.cmd, list | tuple) else "command"
        raise ReadinessError(f"catalog backup readiness command failed: {command}") from exc


def main() -> int:
    try:
        ensure_catalog_backup_ready()
    except (OSError, ReadinessError, ValueError) as exc:
        print(f"catalog backup is not ready: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
