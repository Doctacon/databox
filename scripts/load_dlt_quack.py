#!/usr/bin/env python3
"""Run registered Dagster source jobs in parallel through one Quack server."""

from __future__ import annotations

import argparse
import sys

from databox.config.settings import settings
from databox.config.sources import SOURCES
from databox.orchestration.parallel_refresh import (
    ParallelRefreshError,
    execute_parallel_refresh,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        choices=[source.name for source in SOURCES],
        help="Source to load. Repeat for a subset; default loads every source.",
    )
    parser.add_argument(
        "--database",
        default=settings.database_path,
        help="DuckDB file owned by the shared Quack server.",
    )
    parser.add_argument("--max-workers", type=int)
    parser.add_argument(
        "--skip-sqlmesh",
        action="store_true",
        help="Run ingestion only (for focused diagnostics).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = execute_parallel_refresh(
            args.source,
            database_path=args.database,
            max_workers=args.max_workers,
            run_transform=not args.skip_sqlmesh,
        )
    except ParallelRefreshError as exc:
        for source in exc.result.sources:
            marker = "✓" if source.ok else "✗"
            print(f"{marker} {source.source}: {source.message}")
        print(str(exc), file=sys.stderr)
        return 1

    for source in result.sources:
        print(f"✓ {source.source}: {source.finished_monotonic - source.started_monotonic:.3f}s")
    for item in result.deduped:
        print(f"dedupe {item}")
    for table, count in result.inspection.row_counts:
        print(f"row_count {table}={count}")
    print(f"main_dlt_relations={len(result.inspection.main_dlt_relations)}")
    print(f"overlap_pairs={result.overlap_pairs}")
    print("Parallel Quack refresh complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
