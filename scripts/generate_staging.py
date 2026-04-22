"""Staging-model codegen CLI — thin wrapper over databox.quality.staging_codegen.

Usage:
    python scripts/generate_staging.py              # regenerate staging SQL in place
    python scripts/generate_staging.py --check      # exit 1 if committed SQL drifts

Exit: 0 clean/written · 1 drift · 2 invocation error.
See docs/staging.md for the contract extension and the escape hatch.
"""

from __future__ import annotations

import argparse
import sys

from databox.quality.staging_codegen import check_drift, write_all


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="fail if committed SQL drifts")
    a = p.parse_args(argv)
    try:
        if a.check:
            drifted = check_drift()
            if drifted:
                print("Staging SQL drifted from contracts:", file=sys.stderr)
                for t in drifted:
                    print(f"  - {t}", file=sys.stderr)
                print(
                    "\nRun `python scripts/generate_staging.py` to regenerate, "
                    "or add `-- staging-codegen: skip` to the target SQL if it is hand-maintained.",
                    file=sys.stderr,
                )
                return 1
            print("Staging SQL matches contracts.")
            return 0
        written = write_all()
        for t in written:
            print(f"wrote {t}")
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"staging-codegen error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
