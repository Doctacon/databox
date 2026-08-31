#!/usr/bin/env python3
"""CLI shim for hydrating Pages with the active immutable Rufous release."""

from databox.public_release_hydrate import main

if __name__ == "__main__":
    raise SystemExit(main())
