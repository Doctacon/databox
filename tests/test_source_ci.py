"""Registry-derived source CI contract tests."""

from __future__ import annotations

import fnmatch
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml
from databox.config.sources import SOURCES

SCRIPT = Path(__file__).parent.parent / "scripts" / "source_ci.py"
WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yaml"
EXPECTED_MATRIX = {
    "include": [
        {"source": "avonet", "profile": "file_snapshot"},
        {"source": "ebird", "profile": "http"},
        {"source": "gbif", "profile": "http"},
        {"source": "noaa", "profile": "http"},
        {"source": "usgs", "profile": "http"},
        {"source": "usgs_earthquakes", "profile": "http"},
        {"source": "xeno_canto", "profile": "http"},
    ]
}


def _load_module():
    spec = importlib.util.spec_from_file_location("source_ci", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["source_ci"] = module
    spec.loader.exec_module(module)
    return module


def _source_related_patterns() -> list[str]:
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    filters = workflow["jobs"]["changes"]["steps"][1]["with"]["filters"]
    lines = filters.splitlines()
    start = lines.index("source_related:") + 1
    patterns: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            patterns.append(stripped[2:].strip("'\""))
    return patterns


def test_matrix_is_exact_and_deterministic() -> None:
    module = _load_module()
    assert module.build_matrix() == EXPECTED_MATRIX
    assert module.build_matrix(list(reversed(SOURCES))) == EXPECTED_MATRIX


def test_matrix_rejects_every_registry_level_contract_error() -> None:
    module = _load_module()
    cases = [
        [*SOURCES[:-1], replace(SOURCES[-1], verification_profile=cast(Any, "database"))],
        [*SOURCES, replace(SOURCES[0], name="Bad_Name")],
        [*SOURCES, replace(SOURCES[0], name=SOURCES[1].name)],
        [
            *SOURCES,
            replace(SOURCES[0], name="second_anchor", analytics_anchor=True),
        ],
        [*SOURCES, replace(SOURCES[0], name="empty_tables", raw_tables=())],
    ]
    for invalid in cases:
        with pytest.raises(ValueError, match="invalid canonical source registry"):
            module.build_matrix(invalid)


@pytest.mark.parametrize(
    ("relative", "content"),
    [
        ("packages/databox/databox/config/pipeline_config.py", "# retired authority\n"),
        (
            "packages/databox/databox/consumer.py",
            "from databox_sources.registry import get_registry\n",
        ),
        (
            "packages/databox/databox/consumer.py",
            "from databox.config import pipeline_config\n",
        ),
        (
            "packages/databox/databox/consumer.py",
            "from databox.quality import engine\n",
        ),
        (
            "packages/databox/databox/consumer.py",
            "from databox_sources import base\n",
        ),
        (
            "packages/databox/databox/consumer.py",
            "from databox_sources import registry\n",
        ),
    ],
)
def test_matrix_rejects_reintroduced_legacy_authority(
    monkeypatch, tmp_path: Path, relative: str, content: str
) -> None:
    module = _load_module()
    monkeypatch.setattr(module.check_source_layout, "PROJECT_ROOT", tmp_path)
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    with pytest.raises(ValueError, match="legacy authority"):
        module.build_matrix()


def test_future_registry_entry_automatically_joins_matrix() -> None:
    module = _load_module()
    future = replace(SOURCES[0], name="future_source")
    payload = module.build_matrix([*SOURCES, future])
    assert {entry["source"] for entry in payload["include"]} == {
        *(source.name for source in SOURCES),
        "future_source",
    }


def test_contract_validation_consumes_complete_checker_failures(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module.check_source_layout,
        "validate_sources",
        lambda sources: SimpleNamespace(
            errors=[
                "avonet: packages/databox-sources/tests/avonet/test_schema.py",
                "avonet: incomplete scaffold (scaffolded)",
                "avonet: scheduled source exports daily_pipeline and schedule",
            ]
        ),
    )
    with pytest.raises(ValueError, match="test_schema.py") as error:
        module.validate_contract([SOURCES[0]])
    assert "incomplete scaffold" in str(error.value)
    assert "daily_pipeline" in str(error.value)


def test_coverage_uses_isolated_shared_and_per_source_processes() -> None:
    module = _load_module()
    commands = module.source_coverage_commands(python="python")
    assert len(commands) == len(EXPECTED_MATRIX["include"]) + 1
    shared = commands[0]
    assert "packages/databox-sources/tests/test_vcr_sanitization.py" in shared
    assert "--record-mode=none --block-network" in shared[-1]
    for command, entry in zip(commands[1:], EXPECTED_MATRIX["include"], strict=True):
        path = f"packages/databox-sources/tests/{entry['source']}"
        assert command[:6] == ["python", "-m", "coverage", "run", "--append", "-m"]
        assert path in command
        assert "--record-mode=none --block-network" in command[-1]


@pytest.mark.parametrize(
    "path",
    [
        "packages/databox-sources/databox_sources/avonet/source.py",
        "packages/databox-sources/databox_sources/gbif/source.py",
        "packages/databox-sources/databox_sources/usgs_earthquakes/source.py",
        "packages/databox-sources/databox_sources/xeno_canto/source.py",
        "packages/databox-sources/tests/gbif/test_schema.py",
        "packages/databox/databox/config/sources.py",
        "packages/databox/databox/orchestration/domains/gbif.py",
        "packages/databox/databox/destinations/quack.py",
        "scripts/new_source.py",
        ".github/workflows/ci.yaml",
        "pyproject.toml",
        "uv.lock",
    ],
)
def test_omitted_source_and_shared_paths_trigger_complete_matrix(path: str) -> None:
    patterns = _source_related_patterns()
    assert any(fnmatch.fnmatch(path, pattern) for pattern in patterns), path


def test_workflow_consumes_registry_matrix_without_source_names() -> None:
    text = WORKFLOW.read_text()
    assert "fromJSON(needs.source-matrix.outputs.matrix)" in text
    assert "scripts/source_ci.py matrix" in text
    assert "scripts/source_ci.py coverage" in text
    assert "packages/databox-sources/tests/test_*.py" in text
    assert "src_ebird" not in text
    assert "tests-ebird" not in text
    for entry in EXPECTED_MATRIX["include"]:
        assert f"tests-{entry['source']}" not in text


def test_workflow_actions_remain_commit_pinned() -> None:
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            action: Any = step.get("uses")
            if action is None:
                continue
            assert "@" in action
            revision = action.rsplit("@", maxsplit=1)[1].split()[0]
            assert len(revision) == 40 and all(char in "0123456789abcdef" for char in revision)
