#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
venv_dir=${VENV_DIR:-.venv}
sqlmesh="$repo/$venv_dir/bin/sqlmesh"

cd "$repo/transforms/main"
"$sqlmesh" --log-to-stdout --log-file-dir ../../.logs/sqlmesh-public-media \
  plan prod \
  --select-model rufous_public.usfws_commercial_image \
  --auto-apply \
  --no-prompts \
  --skip-tests
