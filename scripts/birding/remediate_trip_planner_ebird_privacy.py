#!/usr/bin/env python3
"""Inspect or atomically remove saved plans tainted by ineligible eBird evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
from databox.agent_tools.trip_plan_privacy_remediation import (
    inspect_trip_plan_privacy,
    remediate_trip_plan_privacy,
)
from databox.config.settings import settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-path", default=settings.database_path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true", help="Read aggregate counts only")
    mode.add_argument("--apply", action="store_true", help="Delete complete tainted aggregates")
    args = parser.parse_args()

    path = Path(args.database_path)
    if not path.is_file():
        raise SystemExit("warehouse is unavailable")
    connection = duckdb.connect(str(path), read_only=bool(args.inspect))
    try:
        result = (
            inspect_trip_plan_privacy(connection)
            if args.inspect
            else remediate_trip_plan_privacy(connection)
        )
    finally:
        connection.close()
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
