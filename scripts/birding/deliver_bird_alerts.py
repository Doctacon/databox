#!/usr/bin/env python3
"""Explicitly deliver at most one persisted bird-alert outbox row."""

from __future__ import annotations

from datetime import UTC, datetime

import duckdb
from databox.bird_alert_delivery import deliver_next_outbox, settings_from_global
from databox.config.settings import settings


def main() -> int:
    try:
        configured = settings_from_global(settings)
        connection = duckdb.connect(settings.database_path)
    except Exception:
        print("bird alert delivery unavailable (details redacted)")
        return 1
    try:
        try:
            result = deliver_next_outbox(connection, settings=configured, now=datetime.now(UTC))
        except Exception:
            print("bird alert delivery failed (details redacted)")
            return 1
    finally:
        connection.close()
    # Only bounded state/reason are emitted; no server or identity configuration.
    print(f"bird alert delivery: {result.status} ({result.safe_reason or 'none'})")
    return 1 if result.status in {"failed", "delivery_unknown"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
