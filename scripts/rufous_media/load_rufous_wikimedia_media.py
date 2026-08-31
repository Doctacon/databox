#!/usr/bin/env python3
"""CLI shim for the offline curated Wikimedia Commons media snapshot."""

from databox.public_wikimedia_media_ingest import main

if __name__ == "__main__":
    raise SystemExit(main())
