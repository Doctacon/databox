#!/usr/bin/env python3
"""CLI shim for the Rufous hard-zero-cost public release audit."""

from databox.public_export_audit import main

if __name__ == "__main__":
    raise SystemExit(main())
