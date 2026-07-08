#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
venv_dir=${VENV_DIR:-.venv}
python="$repo/$venv_dir/bin/python"
sqlmesh="$repo/$venv_dir/bin/sqlmesh"
state_db="$repo/data/sqlmesh_state.duckdb"

prod_exists() {
  "$python" - "$state_db" <<'PY'
import pathlib
import sys

import duckdb

state_db = pathlib.Path(sys.argv[1])
if not state_db.exists():
    sys.exit(1)

con = duckdb.connect(str(state_db), read_only=True)
try:
    exists = con.execute(
        "SELECT 1 FROM sqlmesh._environments WHERE name = ?",
        ["prod"],
    ).fetchone()
finally:
    con.close()

sys.exit(0 if exists else 1)
PY
}

cd "$repo/transforms/main"
if prod_exists; then
  "$sqlmesh" --log-to-stdout --log-file-dir ../../.logs/sqlmesh \
    plan prod --auto-apply --restate-model "*" --no-prompts
else
  "$sqlmesh" --log-to-stdout --log-file-dir ../../.logs/sqlmesh \
    plan prod --auto-apply --no-prompts
fi
