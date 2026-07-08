#!/usr/bin/env python3
"""Load registered dlt sources through hermetic Quack sessions.

This is the local one-file ingestion path: each source starts a Quack server
over data/databox.duckdb, runs its dlt pipeline into its own raw_<source>
schema, stops Quack, and deduplicates append-loaded rows before the next source.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

# Force the new local path even if a stale .env still says local.
os.environ["DATABOX_BACKEND"] = "quack"
os.environ.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
os.environ.setdefault("SQLMESH__DISABLE_ANONYMIZED_ANALYTICS", "true")

from databox.config.settings import settings
from databox.config.sources import SOURCES
from databox.destinations import (
    cleanup_quack_clients,
    dedupe_quack_raw_tables,
    quack_ingest_session,
)


@dataclass(frozen=True)
class LoadResult:
    source: str
    ok: bool
    message: str


def _load_source(source_name: str, database: str) -> LoadResult:
    os.environ["DATABOX_BACKEND"] = "quack"
    os.environ.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
    os.environ.setdefault("SQLMESH__DISABLE_ANONYMIZED_ANALYTICS", "true")
    try:
        from databox_sources.registry import get_source

        source = get_source(source_name)
        with quack_ingest_session(settings.raw_dataset_name(source_name), db_path=database):
            source.load(smoke=settings.smoke)
        return LoadResult(source_name, True, "loaded")
    except Exception as exc:  # noqa: BLE001 - cross-process report, parent raises summary
        return LoadResult(source_name, False, f"{type(exc).__name__}: {exc}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        choices=[src.name for src in SOURCES],
        help="Source to load. Repeat to load a subset; default loads every registered source.",
    )
    parser.add_argument(
        "--database",
        default=settings.database_path,
        help="DuckDB file the Quack server owns (default: settings.database_path).",
    )
    parser.add_argument(
        "--pipelines-dir",
        default=settings.dlt_data_dir,
        help="dlt state directory (default: settings.dlt_data_dir).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings.dlt_data_dir = args.pipelines_dir
    os.environ["DATABOX_DLT_DATA_DIR"] = args.pipelines_dir
    names = args.source or [src.name for src in SOURCES]
    if not names:
        print("No sources registered.")
        return 0

    print(f"Loading {len(names)} source(s) through hermetic Quack sessions over {args.database}.")
    try:
        results = [_load_source(name, args.database) for name in names]
    finally:
        cleanup_quack_clients()

    deduped = dedupe_quack_raw_tables(args.database)
    for line in deduped:
        print(f"dedupe {line}")

    failures = [r for r in results if not r.ok]
    for result in results:
        marker = "✓" if result.ok else "✗"
        print(f"{marker} {result.source}: {result.message}")

    if failures:
        return 1
    print("Quack dlt load complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
