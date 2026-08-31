#!/usr/bin/env python3
"""CLI shim for Rufous's non-deployable local human media-review app."""

from databox.public_media_review import main

if __name__ == "__main__":
    raise SystemExit(main())
