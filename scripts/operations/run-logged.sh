#!/usr/bin/env bash
# Run a command with output redirected to .logs/<name>-<timestamp>.log.
# While running, render a spinner + elapsed time + STEP_SUCCESS count +
# latest step name (parsed from the live Dagster log). On failure print
# the last 30 lines of the log and propagate the exit code.
# Usage: run-logged.sh <name> -- <command> [args...]
set -u
name="${1:?run-logged.sh: missing <name>}"; shift
[[ "${1:-}" == "--" ]] && shift
mkdir -p .logs
log=".logs/${name}-$(date +%Y%m%d-%H%M%S).log"
echo "→ logging to $log  (tail -f $log to watch)"

"$@" > "$log" 2>&1 &
pid=$!

# Skip the spinner when stderr is not a TTY (CI, piped output).
if [[ -t 2 ]]; then
  spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
  i=0
  start=$SECONDS
  while kill -0 "$pid" 2>/dev/null; do
    elapsed=$((SECONDS - start))
    n=$(grep -c 'STEP_SUCCESS' "$log" 2>/dev/null; true)
    n=${n:-0}
    latest=$(grep 'STEP_SUCCESS' "$log" 2>/dev/null \
      | tail -1 \
      | sed -n 's/.* - \([a-zA-Z0-9_]*\) - STEP_SUCCESS.*/\1/p')
    frame="${spin:$((i % 10)):1}"
    printf "\r\033[K  %s %3ds   %2d steps done%s" \
      "$frame" "$elapsed" "$n" "${latest:+ · last: $latest}" >&2
    i=$((i + 1))
    sleep 0.3
  done
  printf "\r\033[K" >&2
fi

wait "$pid"
rc=$?
if [[ $rc -eq 0 ]]; then
  echo "✓ $name done — $log"
else
  echo "✗ $name failed (exit $rc) — last 30 lines:"
  tail -30 "$log"
  exit "$rc"
fi
