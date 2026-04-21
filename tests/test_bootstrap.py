"""Unit tests for scripts/bootstrap.py.

Exercises the substitution machinery against synthetic file trees — the goal
is to verify ordering (specific → general), safe non-substitution of bare
Python-package-name tokens, and idempotency.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).parent.parent / "scripts" / "bootstrap.py"


def _load_module():
    if "bootstrap" in sys.modules:
        return sys.modules["bootstrap"]
    spec = importlib.util.spec_from_file_location("bootstrap", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["bootstrap"] = module
    spec.loader.exec_module(module)
    return module


def _baseline() -> dict:
    return {
        "project": {
            "name": "Databox",
            "slug": "databox",
            "description": "Databox data platform",
            "copyright_holder": "Connor Lough",
        },
        "github": {"org": "Doctacon", "repo": "databox"},
        "docs": {"site_url": "https://doctacon.github.io/databox/"},
        "bootstrap": {"includes": ["README.md", "pyproject.toml", "LICENSE"]},
    }


def test_no_overrides_produces_empty_substitution_list() -> None:
    module = _load_module()
    old = module.Identity.from_mapping(_baseline())
    new = module.Identity.from_mapping(_baseline())
    assert module.compute_substitutions(old, new) == []


def test_rename_produces_ordered_substitutions() -> None:
    module = _load_module()
    old = module.Identity.from_mapping(_baseline())
    new_data = _baseline()
    new_data["project"]["name"] = "Weatherbox"
    new_data["project"]["slug"] = "weatherbox"
    new_data["github"]["org"] = "example-org"
    new_data["github"]["repo"] = "weatherbox"
    new_data["docs"]["site_url"] = "https://example-org.github.io/weatherbox/"
    new = module.Identity.from_mapping(new_data)
    subs = module.compute_substitutions(old, new)
    # Site URL is most specific → must come before composite GitHub path.
    site_idx = next(i for i, (o, _) in enumerate(subs) if o.startswith("https://"))
    path_idx = next(i for i, (o, _) in enumerate(subs) if o == "Doctacon/databox")
    name_idx = next(i for i, (o, _) in enumerate(subs) if o == "Databox")
    assert site_idx < path_idx < name_idx


def test_apply_subs_rewrites_readme(tmp_path: Path) -> None:
    module = _load_module()
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Databox\n"
        "[CI](https://github.com/Doctacon/databox/actions)\n"
        "See https://doctacon.github.io/databox/ for docs.\n"
    )
    old = module.Identity.from_mapping(_baseline())
    new_data = _baseline()
    new_data["project"]["name"] = "Weatherbox"
    new_data["project"]["slug"] = "weatherbox"
    new_data["github"]["org"] = "example-org"
    new_data["github"]["repo"] = "weatherbox"
    new_data["docs"]["site_url"] = "https://example-org.github.io/weatherbox/"
    new = module.Identity.from_mapping(new_data)
    subs = module.compute_substitutions(old, new)
    changed = module.apply_substitutions([readme], subs)
    assert len(changed) == 1
    out = readme.read_text()
    assert "# Weatherbox" in out
    assert "Doctacon" not in out
    assert "doctacon" not in out
    assert "https://example-org.github.io/weatherbox/" in out


def test_apply_subs_preserves_python_import_name(tmp_path: Path) -> None:
    """Bare lowercase `databox` (Python package) must NOT be substituted."""
    module = _load_module()
    code = tmp_path / "settings.py"
    code.write_text("from databox.config import settings\nimport databox\n")
    old = module.Identity.from_mapping(_baseline())
    new_data = _baseline()
    new_data["project"]["slug"] = "weatherbox"
    new_data["github"]["repo"] = "weatherbox"
    new = module.Identity.from_mapping(new_data)
    subs = module.compute_substitutions(old, new)
    module.apply_substitutions([code], subs)
    assert code.read_text() == "from databox.config import settings\nimport databox\n"


def test_apply_subs_rewrites_workspace_name(tmp_path: Path) -> None:
    module = _load_module()
    pyproj = tmp_path / "pyproject.toml"
    pyproj.write_text('[project]\nname = "databox-workspace"\n')
    old = module.Identity.from_mapping(_baseline())
    new_data = _baseline()
    new_data["project"]["slug"] = "weatherbox"
    new = module.Identity.from_mapping(new_data)
    subs = module.compute_substitutions(old, new)
    module.apply_substitutions([pyproj], subs)
    assert 'name = "weatherbox-workspace"' in pyproj.read_text()


def test_idempotent_second_run_with_same_values(tmp_path: Path) -> None:
    module = _load_module()
    readme = tmp_path / "README.md"
    original = "# Weatherbox\nSee https://example-org.github.io/weatherbox/ for docs.\n"
    readme.write_text(original)
    new_data = _baseline()
    new_data["project"]["name"] = "Weatherbox"
    new_data["project"]["slug"] = "weatherbox"
    new_data["github"]["org"] = "example-org"
    new_data["github"]["repo"] = "weatherbox"
    new_data["docs"]["site_url"] = "https://example-org.github.io/weatherbox/"
    same = module.Identity.from_mapping(new_data)
    subs = module.compute_substitutions(same, same)
    changed = module.apply_substitutions([readme], subs)
    assert changed == []
    assert readme.read_text() == original


def test_resolve_includes_expands_globs(tmp_path: Path) -> None:
    module = _load_module()
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("x")
    (tmp_path / "docs" / "a.md").write_text("x")
    (tmp_path / "docs" / "b.md").write_text("x")
    files = module.resolve_includes(["README.md", "docs/*.md"], root=tmp_path)
    assert [p.relative_to(tmp_path).as_posix() for p in files] == [
        "README.md",
        "docs/a.md",
        "docs/b.md",
    ]


def test_overlay_preserves_unset_fields() -> None:
    module = _load_module()
    data = _baseline()
    out = module.overlay(data, name="Weatherbox")
    assert out["project"]["name"] == "Weatherbox"
    assert out["project"]["slug"] == "databox"
    assert out["github"]["org"] == "Doctacon"


@pytest.mark.parametrize(
    "existing,expected_hit",
    [
        ("Doctacon/databox", True),
        ("https://github.com/Doctacon/databox/pull/1", True),
        ("doctacon.github.io/databox", True),
        ("databox-workspace", True),
        ("# Databox", True),
        ("from databox import foo", False),  # bare lowercase untouched
        ("databox-sources", False),  # bare lowercase untouched
    ],
)
def test_substitution_coverage(tmp_path: Path, existing: str, expected_hit: bool) -> None:
    module = _load_module()
    f = tmp_path / "file.md"
    f.write_text(existing)
    old = module.Identity.from_mapping(_baseline())
    new_data = _baseline()
    new_data["project"]["name"] = "Weatherbox"
    new_data["project"]["slug"] = "weatherbox"
    new_data["github"]["org"] = "example-org"
    new_data["github"]["repo"] = "weatherbox"
    new_data["docs"]["site_url"] = "https://example-org.github.io/weatherbox/"
    new = module.Identity.from_mapping(new_data)
    subs = module.compute_substitutions(old, new)
    module.apply_substitutions([f], subs)
    was_changed = f.read_text() != existing
    assert was_changed == expected_hit


def test_scaffold_yaml_round_trips_identity() -> None:
    """scaffold.yaml at repo root must parse cleanly into an Identity."""
    module = _load_module()
    data = yaml.safe_load((module.ROOT / "scaffold.yaml").read_text())
    identity = module.Identity.from_mapping(data)
    assert identity.name
    assert identity.slug
    assert identity.org
    assert identity.repo
    assert identity.site_url.startswith("https://")
