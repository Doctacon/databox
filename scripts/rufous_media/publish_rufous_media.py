#!/usr/bin/env python3
"""CLI shim for immutable Rufous public-media publication."""

from databox.public_media_release import main

if __name__ == "__main__":
    raise SystemExit(main())
