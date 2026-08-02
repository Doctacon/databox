#!/usr/bin/env python3
"""CLI shim for atomic Rufous public-data publication."""

from databox.public_release import main

if __name__ == "__main__":
    raise SystemExit(main())
