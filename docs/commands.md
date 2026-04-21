# Commands Cheatsheet

`Taskfile.yaml` only keeps targets that **compose multiple commands**,
**inject environment variables**, or **encode a non-obvious default**.
Everything else is a direct call into a third-party CLI — listed below
so a forker can run the underlying command without learning a Task
target that merely renamed it.

All `uv run` commands assume you are at the repo root.

## Linting + formatting

```bash
uv run ruff check .                  # lint
uv run ruff check . --fix            # lint + auto-fix
uv run ruff format .                 # format in place
uv run ruff format --check .         # format check (no write)
uv run mypy . --ignore-missing-imports
```

`task ci` composes all four gates plus pytest + secret scan.

## Testing

```bash
uv run pytest                        # full suite
uv run pytest -m unit                # unit tests only
uv run pytest -m integration         # integration tests
uv run pytest -m e2e                 # end-to-end tests
uv run pytest --cov=. --cov-report=html
```

Test markers are defined in `pyproject.toml` under `[tool.pytest.ini_options]`.

## SQLMesh

Run from `transforms/main/` — SQLMesh picks up `config.py` there.

```bash
cd transforms/main
uv run sqlmesh plan --auto-apply     # plan + apply changes
uv run sqlmesh run                   # run scheduled models
uv run sqlmesh test                  # run SQLMesh unit tests
uv run sqlmesh ui                    # start SQLMesh UI
uv run sqlmesh plan dev              # plan into dev env
```

## Dagster (beyond `dagster:dev` / `full-refresh` / `verify`)

```bash
export DAGSTER_HOME="$PWD/.dagster"
export PYTHONPATH="$PWD"

uv run dagster asset materialize --select <key> \
  -f packages/databox/databox/orchestration/definitions.py

uv run dagster asset wipe --all \
  -f packages/databox/databox/orchestration/definitions.py
```

## Pre-commit

```bash
uv run pre-commit run --all-files    # run every hook across every file
uv run pre-commit run ruff           # run one hook
```

## Secret scan

```bash
python scripts/check_secrets.py      # scan repo root
python scripts/check_secrets.py path/to/file.py
```

## Source layout + staging codegen

```bash
python scripts/check_source_layout.py        # lint per-source directory layout
python scripts/generate_staging.py           # regenerate trivial-rename stg_* SQL
python scripts/generate_staging.py --check   # fail on drift (also runs in task ci)
```

## Watching

Task's built-in watch mode works without a dedicated target:

```bash
task -w ci                           # re-run ci on file change
```
