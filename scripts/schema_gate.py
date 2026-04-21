"""Schema-contract gate CLI — thin wrapper over databox.quality.schema_gate.

Usage:
    python scripts/schema_gate.py --base origin/main
    python scripts/schema_gate.py --base origin/main --accept ebird.fct_daily_bird_observations

Exit: 0 clean or acked · 1 unacked breaking · 2 invocation error.
See docs/contracts.md for the classifier and acknowledgement protocol.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from databox.quality.schema_gate import (
    acknowledgements,
    contracts_at_head,
    contracts_at_revision,
    diff,
    format_report,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="origin/main")
    p.add_argument("--pr-body-file", default=None)
    p.add_argument("--accept", default=None)
    a = p.parse_args(argv)
    try:
        report = diff(contracts_at_revision(a.base), contracts_at_head())
        body = Path(a.pr_body_file).read_text() if a.pr_body_file else None
        acked = acknowledgements(body, a.accept or os.environ.get("ACCEPT_BREAKING_CHANGE"))
        print(format_report(report, acked))
        if any(c.model not in acked for c in report.breaking):
            print("\nFAIL: unacknowledged breaking changes.", file=sys.stderr)
            print(
                "Acknowledge via `accept-breaking-change: <dataset>` in PR body.",
                file=sys.stderr,
            )
            return 1
        if report.breaking:
            print("\nAll breaking changes acknowledged.")
        return 0
    except RuntimeError as exc:
        print(f"schema-gate error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
