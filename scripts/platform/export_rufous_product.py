#!/usr/bin/env python3
"""Export the local versioned Databox product consumed by Rufous."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
from databox.config.settings import settings
from databox.product_artifact import (
    ProductArtifactError,
    export_rufous_product,
    require_distinct_database_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(settings.database_path))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        require_distinct_database_paths(args.source, args.output)
    except ProductArtifactError as error:
        parser.error(str(error))
    if not args.source.is_file():
        parser.error(f"source database is not a regular file: {args.source}")
    source = duckdb.connect(str(args.source), read_only=True)
    try:
        settings.attach_iceberg_to_duckdb(source)
        destination = export_rufous_product(source, args.output)
    finally:
        source.close()
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
