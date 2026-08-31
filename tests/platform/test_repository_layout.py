"""Repository-level contracts for domain-organized tests and scripts."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_root_tests_are_grouped_by_ratified_domain() -> None:
    tests_dir = PROJECT_ROOT / "tests"

    assert not list(tests_dir.glob("test_*.py"))
    assert {
        path.name
        for path in tests_dir.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    } == {
        "analytics",
        "birding",
        "cloudflare",
        "evals",
        "platform",
        "rufous_media",
        "sources",
    }


def test_root_scripts_are_grouped_by_ratified_domain() -> None:
    scripts_dir = PROJECT_ROOT / "scripts"

    assert not [
        path.name
        for path in scripts_dir.iterdir()
        if path.is_file() and path.suffix in {".py", ".sh", ".sql"}
    ]
    assert {
        path.name
        for path in scripts_dir.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    } == {
        "analytics",
        "birding",
        "cloudflare",
        "operations",
        "platform",
        "rufous_media",
        "sources",
    }
    assert (scripts_dir / "analytics/templates/staging.sql.j2").is_file()
    assert (scripts_dir / "sources/templates/source/common/domain.py.j2").is_file()


@pytest.mark.parametrize(
    ("script_path", "expected_plans"),
    [
        ("scripts/analytics/sqlmesh_plan_prod.sh", 1),
        ("scripts/rufous_media/sqlmesh_plan_rufous_inaturalist_media.sh", 1),
        ("scripts/rufous_media/sqlmesh_plan_rufous_media.sh", 1),
        ("scripts/rufous_media/sqlmesh_plan_rufous_public.sh", 2),
    ],
)
def test_moved_sqlmesh_scripts_resolve_the_repository_root(
    tmp_path: Path, script_path: str, expected_plans: int
) -> None:
    repository = tmp_path / "repository"
    copied_script = repository / script_path
    copied_script.parent.mkdir(parents=True)
    shutil.copyfile(PROJECT_ROOT / script_path, copied_script)
    (repository / "transforms/main").mkdir(parents=True)

    bin_dir = repository / ".venv/bin"
    bin_dir.mkdir(parents=True)
    sqlmesh = bin_dir / "sqlmesh"
    sqlmesh.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\t%s\\t%s\\n" "$PWD" "$0" "$*" >> "$SQLMESH_CAPTURE"\n',
        encoding="utf-8",
    )
    sqlmesh.chmod(0o755)
    python = bin_dir / "python"
    python.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    python.chmod(0o755)

    capture = tmp_path / "sqlmesh-invocations.tsv"
    result = subprocess.run(  # noqa: S603
        ["bash", str(copied_script)],
        cwd=repository,
        env=os.environ | {"VENV_DIR": ".venv", "SQLMESH_CAPTURE": str(capture)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    invocations = [line.split("\t", maxsplit=2) for line in capture.read_text().splitlines()]
    assert len(invocations) == expected_plans
    assert all(Path(cwd) == repository / "transforms/main" for cwd, _, _ in invocations)
    assert all(Path(executable) == sqlmesh for _, executable, _ in invocations)
