#!/usr/bin/env python3
"""Load GBIF occurrences into the configured existing Polaris Iceberg catalog."""

from __future__ import annotations

import os

from databox.config.settings import settings
from databox_sources.gbif.iceberg import load_gbif_occurrences

if __name__ == "__main__":
    result = load_gbif_occurrences(
        catalog=settings.pyiceberg_catalog(),
        max_records=int(os.getenv("DATABOX_GBIF_MAX_RECORDS", "10")),
    )
    print(
        f"gbif_iceberg rows={result.row_count} inserted={result.rows_inserted} "
        f"updated={result.rows_updated} snapshot_id={result.snapshot_id}"
    )
