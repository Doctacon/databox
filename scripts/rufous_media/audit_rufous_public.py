#!/usr/bin/env python3
"""CLI shim for the Rufous public release safety audit."""

from databox.public_export_audit import main

if __name__ == "__main__":
    raise SystemExit(main())
