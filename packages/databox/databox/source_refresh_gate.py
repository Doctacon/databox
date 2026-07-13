"""Pre-mutation gate for the durable Rufous source-refresh runner."""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command or args.command[0] != "--":
        return 2
    if sys.stdin.readline() != f"GO {args.run_id}\n":
        return 1
    return subprocess.run(args.command[1:], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
