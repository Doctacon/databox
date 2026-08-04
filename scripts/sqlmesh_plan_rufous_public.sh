#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
venv_dir=${VENV_DIR:-.venv}
sqlmesh="$repo/$venv_dir/bin/sqlmesh"

cd "$repo/transforms/main"
for model in \
  rufous_public.gbif_eod_occurrence \
  rufous_public.avonet_species_traits
do
  "$sqlmesh" --log-to-stdout --log-file-dir ../../.logs/sqlmesh-public \
    plan prod \
    --select-model "$model" \
    --auto-apply \
    --no-prompts \
    --skip-tests
done
