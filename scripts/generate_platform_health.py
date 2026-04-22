"""Regenerate `analytics/platform_health.sql` from the source registry.

Usage:
    python scripts/generate_platform_health.py              # regenerate in place
    python scripts/generate_platform_health.py --check      # exit 1 if committed drifts

Exit: 0 clean/written · 1 drift · 2 invocation error.
"""

from __future__ import annotations

import argparse
import sys

from databox.quality.platform_health_codegen import TARGET, check_drift, write


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="fail if committed SQL drifts")
    a = p.parse_args(argv)
    try:
        if a.check:
            if check_drift():
                print(f"{TARGET} drifted from source registry.", file=sys.stderr)
                print(
                    "Run `python scripts/generate_platform_health.py` to regenerate.",
                    file=sys.stderr,
                )
                return 1
            print(f"{TARGET} matches source registry.")
            return 0
        path = write()
        print(f"wrote {path}")
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"platform-health-codegen error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
