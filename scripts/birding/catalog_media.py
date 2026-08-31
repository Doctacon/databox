#!/usr/bin/env python3
"""Inspect or explicitly run a bounded Arizona catalog-media batch."""

from __future__ import annotations

import argparse
import json

from databox.catalog_media import (
    catalog_media_prerequisites,
    inspect_catalog_photo_refresh,
    run_catalog_media_batch,
    run_catalog_photo_refresh,
)
from databox.config.settings import settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-path", default=settings.database_path)
    parser.add_argument("--batch-size", type=int, default=25)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-prerequisites", action="store_true")
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--refresh", action="store_true")
    mode.add_argument("--dry-run-photos", action="store_true")
    mode.add_argument("--refresh-photos", action="store_true")
    args = parser.parse_args()
    if args.check_prerequisites:
        print(json.dumps(catalog_media_prerequisites(), sort_keys=True))
        return 0
    if args.dry_run_photos:
        import duckdb

        connection = duckdb.connect(args.database_path, read_only=True)
        try:
            result = inspect_catalog_photo_refresh(connection)
        finally:
            connection.close()
    elif args.refresh_photos:
        result = run_catalog_photo_refresh(args.database_path, batch_size=args.batch_size)
    else:
        selected = "inspect" if args.inspect else "refresh" if args.refresh else "apply"
        result = run_catalog_media_batch(
            args.database_path, mode=selected, batch_size=args.batch_size
        )
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
