#!/usr/bin/env python3
"""CLI shim for the Rufous public static-data exporter."""

from databox.public_export import main

if __name__ == "__main__":
    raise SystemExit(main())
