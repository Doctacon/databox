#!/usr/bin/env python3
"""CLI shim for composing or verifying the provider-free Rufous media pin."""

from databox.public_media_pin import main

if __name__ == "__main__":
    raise SystemExit(main())
