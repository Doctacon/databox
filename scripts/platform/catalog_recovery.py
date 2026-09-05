#!/usr/bin/env python3
"""Fail-closed helpers for an isolated Polaris catalog recovery drill."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def recovery_target(value: str) -> datetime:
    target = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if target.tzinfo is None:
        raise ValueError("Recovery target must include a timezone")
    return target.astimezone(UTC)


def require_empty_isolated_target(target: Path, active: Path) -> Path:
    target = target.resolve()
    active = active.resolve()
    if target == active:
        raise ValueError("Recovery target must not be the active PostgreSQL volume")
    if target.exists() and any(target.iterdir()):
        raise ValueError("Recovery target must be empty")
    target.mkdir(parents=True, exist_ok=True)
    return target


def drill_result(started: datetime, recovered_to: datetime, finished: datetime) -> dict[str, Any]:
    return {
        "started_at": started.astimezone(UTC).isoformat(),
        "finished_at": finished.astimezone(UTC).isoformat(),
        "recovered_to": recovered_to.astimezone(UTC).isoformat(),
        "achieved_rpo_seconds": max(0, int((started - recovered_to).total_seconds())),
        "achieved_rto_seconds": max(0, int((finished - started).total_seconds())),
        "objectives_proven": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--active", required=True, type=Path)
    parser.add_argument("--recover-to", required=True)
    parser.add_argument("--prepare-only", action="store_true", required=True)
    args = parser.parse_args()
    target = require_empty_isolated_target(args.target, args.active)
    recover_to = recovery_target(args.recover_to)
    print(
        json.dumps(
            {
                "target": str(target),
                "recover_to": recover_to.isoformat(),
                "writers": "disabled",
                "bootstrap": "forbidden",
                "authoritative_backup_archive": "disabled",
                "next": "run reviewed pgBackRest restore; do not cut over",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
