#!/usr/bin/env python3
"""Inspect or explicitly run a bounded Arizona catalog-media batch."""

from __future__ import annotations

import argparse
import json

from databox.catalog_media import catalog_media_prerequisites, run_catalog_media_batch
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
    args = parser.parse_args()
    if args.check_prerequisites:
        print(json.dumps(catalog_media_prerequisites(), sort_keys=True))
        return 0
    selected = "inspect" if args.inspect else "refresh" if args.refresh else "apply"
    result = run_catalog_media_batch(args.database_path, mode=selected, batch_size=args.batch_size)
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
