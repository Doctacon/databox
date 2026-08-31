#!/usr/bin/env python3
"""Explicit redacted Proton Bridge/generic SMTP alert verification."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

import duckdb
from databox.bird_alert_delivery import (
    preflight_smtp,
    send_bounded_live_verification,
    settings_from_global,
)
from databox.config.settings import settings


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--test-email", action="store_true")
    mode.add_argument("--test-invitation", action="store_true")
    args = parser.parse_args()
    try:
        configured = settings_from_global(settings)
    except Exception:
        print("alert SMTP configuration validation failed (details redacted)")
        return 1
    if args.preflight:
        try:
            preflight_smtp(configured)
        except Exception:
            print("alert SMTP preflight failed (details redacted; no message sent)")
            return 1
        print("alert SMTP preflight passed (configuration redacted; no message sent)")
        return 0
    kind = "test_email" if args.test_email else "test_invitation"
    connection = duckdb.connect(settings.database_path)
    try:
        try:
            result = send_bounded_live_verification(
                connection,
                settings=configured,
                kind=kind,
                now=datetime.now(UTC),
            )
        except Exception:
            print(f"alert SMTP {kind} verification unavailable (details redacted)")
            return 1
    finally:
        connection.close()
    print(f"alert SMTP {kind} verification result: {result} (configuration redacted)")
    return 0 if result == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
