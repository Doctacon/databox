"""Unit tests for databox.quality.staging_codegen.

Exercises the contract parser, the renderer, and the skip-marker logic.
End-to-end regeneration against real contracts is covered by the
`staging-codegen-drift` CI job.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from databox.quality.staging_codegen import (
    Column,
    StagingModel,
    check_drift,
    is_skipped,
    parse_contract,
    render,
)


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


# --------------------------------------------------------------------------- #
# parse_contract
# --------------------------------------------------------------------------- #


def test_parse_full_contract(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "soda/contracts/foo_staging/stg_foo_bar.yaml",
        """
dataset: databox/foo_staging/stg_foo_bar
source_table: raw_foo.main.bar
description: Hello
columns:
  - name: id
  - name: created_at
    source_column: _created_at
    data_type: TIMESTAMP
  - name: latitude
    data_type: DOUBLE
""",
    )
    model = parse_contract(p)
    assert model is not None
    assert model.schema == "foo_staging"
    assert model.table == "stg_foo_bar"
    assert model.source_table == "raw_foo.main.bar"
    assert model.description == "Hello"
    assert [c.name for c in model.columns] == ["id", "created_at", "latitude"]
    assert model.columns[0].source_column == "id"
    assert model.columns[0].data_type is None
    assert model.columns[1].source_column == "_created_at"
    assert model.columns[1].data_type == "TIMESTAMP"


def test_parse_non_staging_returns_none(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "soda/contracts/foo/fct_bar.yaml",
        "dataset: databox/foo/fct_bar\ncolumns: []\n",
    )
    assert parse_contract(p) is None


def test_parse_missing_source_table_raises(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "soda/contracts/foo_staging/stg_x.yaml",
        "dataset: databox/foo_staging/stg_x\ncolumns: []\n",
    )
    with pytest.raises(ValueError, match="source_table"):
        parse_contract(p)


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #


def _model(columns: list[Column]) -> StagingModel:
    return StagingModel(
        contract_path=Path("soda/contracts/foo_staging/stg_foo.yaml"),
        target_path=Path("transforms/main/models/foo/staging/stg_foo.sql"),
        schema="foo_staging",
        table="stg_foo",
        description="Foo staging",
        source_table="raw_foo.main.bar",
        columns=columns,
    )


def test_render_identity_column() -> None:
    sql = render(_model([Column("id", "id", None)]))
    assert "    id\n" in sql
    assert "FROM raw_foo.main.bar" in sql


def test_render_rename_only() -> None:
    sql = render(_model([Column("location_id", "loc_id", None)]))
    assert "    loc_id AS location_id\n" in sql


def test_render_cast_with_rename() -> None:
    sql = render(_model([Column("latitude", "lat", "DOUBLE")]))
    assert "    lat::DOUBLE AS latitude\n" in sql


def test_render_cast_identity_name() -> None:
    sql = render(_model([Column("value", "value", "DOUBLE")]))
    assert "    value::DOUBLE AS value\n" in sql


def test_render_trailing_comma_rules() -> None:
    sql = render(
        _model(
            [
                Column("a", "a", None),
                Column("b", "b", None),
                Column("c", "c", None),
            ]
        )
    )
    lines = [line.rstrip() for line in sql.splitlines()]
    assert "    a," in lines
    assert "    b," in lines
    assert "    c" in lines
    assert "    c," not in lines


def test_render_header_comment_and_model() -> None:
    sql = render(_model([Column("id", "id", None)]))
    assert sql.startswith("-- Generated from soda/contracts/foo_staging/stg_foo.yaml")
    assert "MODEL (\n  name foo_staging.stg_foo,\n  kind FULL," in sql
    assert "grants (select_ = ['staging_reader'])" in sql


def test_render_escapes_single_quote_in_description() -> None:
    model = _model([Column("id", "id", None)])
    model.description = "It's staging"
    assert "description 'It''s staging'" in render(model)


# --------------------------------------------------------------------------- #
# is_skipped / check_drift
# --------------------------------------------------------------------------- #


def test_is_skipped_recognises_marker(tmp_path: Path) -> None:
    p = _write(tmp_path / "a.sql", "-- staging-codegen: skip\nMODEL (...)\n")
    assert is_skipped(p)


def test_is_skipped_false_without_marker(tmp_path: Path) -> None:
    p = _write(tmp_path / "a.sql", "MODEL (...)\n")
    assert not is_skipped(p)


def test_is_skipped_false_on_missing_file(tmp_path: Path) -> None:
    assert not is_skipped(tmp_path / "nope.sql")


def test_check_drift_clean_after_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Anchor the codegen at a temp workspace and verify a regenerated file is drift-free.
    contracts_root = tmp_path / "soda" / "contracts"
    _write(
        contracts_root / "foo_staging" / "stg_foo.yaml",
        """
dataset: databox/foo_staging/stg_foo
source_table: raw_foo.main.bar
description: Foo
columns:
  - name: id
""",
    )
    models_root = tmp_path / "transforms" / "main" / "models"
    models_root.mkdir(parents=True)

    import databox.quality.staging_codegen as mod

    monkeypatch.setattr(mod, "CONTRACTS_DIR", contracts_root)
    monkeypatch.setattr(mod, "MODELS_DIR", models_root)
    # Template path is relative to CWD; chdir into repo root (it owns the template).
    monkeypatch.chdir(Path(__file__).parent.parent)

    written = mod.write_all(contracts_root)
    assert len(written) == 1
    assert check_drift(contracts_root) == []
