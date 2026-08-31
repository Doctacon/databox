#!/usr/bin/env python3
"""CLI shim for Rufous's committed human media-approval gate."""

from databox.public_media_approval import main

if __name__ == "__main__":
    raise SystemExit(main())
