#!/usr/bin/env python3
"""CLI shim for the public USFWS bird-media dlt snapshot."""

from databox.public_media_ingest import main

if __name__ == "__main__":
    raise SystemExit(main())
