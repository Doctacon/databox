#!/usr/bin/env bash
# Run a command with output redirected to .logs/<name>-<timestamp>.log.
# On failure print the last 30 lines of the log and propagate the exit code.
# Usage: run-logged.sh <name> -- <command> [args...]
set -u
name="${1:?run-logged.sh: missing <name>}"; shift
[[ "${1:-}" == "--" ]] && shift
mkdir -p .logs
log=".logs/${name}-$(date +%Y%m%d-%H%M%S).log"
echo "→ logging to $log  (tail -f $log to watch)"
if "$@" > "$log" 2>&1; then
  echo "✓ $name done — $log"
else
  rc=$?
  echo "✗ $name failed (exit $rc) — last 30 lines:"
  tail -30 "$log"
  exit "$rc"
fi
