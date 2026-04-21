"""Unit tests for databox.quality.schema_gate classifier.

Exercises the diff classifier in isolation — no git, no file I/O.
CI covers the end-to-end path with a real `origin/main` base ref.
"""

from __future__ import annotations

from databox.quality.schema_gate import acknowledgements, diff, widens


def _contract(dataset: str, columns: list[dict[str, object]]) -> str:
    lines = [f"dataset: {dataset}", "columns:"]
    for col in columns:
        lines.append(f"  - name: {col['name']}")
        if "data_type" in col:
            lines.append(f"    data_type: {col['data_type']}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# diff classifier
# --------------------------------------------------------------------------- #


def test_add_column_is_additive() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "a"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "a"}, {"name": "b"}])}
    report = diff(base, head)
    assert not report.has_breaking
    assert len(report.additive) == 1
    assert report.additive[0].kind == "column_added"
    assert "b" in report.additive[0].detail


def test_drop_column_is_breaking() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "a"}, {"name": "b"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "a"}])}
    report = diff(base, head)
    assert report.has_breaking
    assert report.breaking[0].kind == "column_removed"
    assert "b" in report.breaking[0].detail


def test_rename_column_shows_as_drop_plus_add() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "old_name"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "new_name"}])}
    report = diff(base, head)
    assert any(c.kind == "column_removed" for c in report.breaking)
    assert any(c.kind == "column_added" for c in report.additive)


def test_widen_type_is_additive() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "int"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "bigint"}])}
    report = diff(base, head)
    assert not report.has_breaking


def test_narrow_type_is_breaking() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "bigint"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "int"}])}
    report = diff(base, head)
    assert report.has_breaking
    assert report.breaking[0].kind == "type_narrowed"


def test_int_to_float_is_additive() -> None:
    # New edge case — covered by sqlglot's NUMERIC_TYPES superset
    base = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "int"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "double"}])}
    assert not diff(base, head).has_breaking


def test_date_to_timestamp_is_additive() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "date"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "timestamp"}])}
    assert not diff(base, head).has_breaking


def test_timestamp_to_date_is_breaking() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "timestamp"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "date"}])}
    assert diff(base, head).has_breaking


def test_varchar_to_text_is_additive() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "varchar"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "a", "data_type": "text"}])}
    assert not diff(base, head).has_breaking


def test_add_model_is_additive() -> None:
    base: dict[str, str] = {}
    head = {"c.yaml": _contract("x.y", [{"name": "a"}])}
    report = diff(base, head)
    assert not report.has_breaking
    assert report.additive[0].kind == "model_added"


def test_remove_model_is_breaking() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "a"}])}
    head: dict[str, str] = {}
    report = diff(base, head)
    assert report.has_breaking
    assert report.breaking[0].kind == "model_removed"


def test_rename_model_is_breaking() -> None:
    base = {"c.yaml": _contract("x.old", [{"name": "a"}])}
    head = {"c.yaml": _contract("x.new", [{"name": "a"}])}
    report = diff(base, head)
    assert any(c.kind == "model_renamed" for c in report.breaking)


def test_no_changes_is_clean() -> None:
    base = {"c.yaml": _contract("x.y", [{"name": "a"}])}
    head = {"c.yaml": _contract("x.y", [{"name": "a"}])}
    report = diff(base, head)
    assert not report.has_breaking
    assert not report.additive


# --------------------------------------------------------------------------- #
# widens() directly
# --------------------------------------------------------------------------- #


def test_widens_unknown_types_fail_closed() -> None:
    # Unknown type on either side → treat as narrowing (fail closed)
    assert not widens("definitely_not_a_type", "int")
    assert not widens("int", "also_bogus")


def test_widens_same_string_is_identity() -> None:
    assert widens("int", "int")
    assert widens("INT", "int")  # case-insensitive


# --------------------------------------------------------------------------- #
# acknowledgement parsing
# --------------------------------------------------------------------------- #


def test_ack_from_env_only() -> None:
    assert acknowledgements(pr_body=None, env="a.b, c.d") == {"a.b", "c.d"}


def test_ack_from_pr_body_single() -> None:
    body = "Some PR summary\n\naccept-breaking-change: ebird.fct_daily_bird_observations\n"
    assert acknowledgements(body, None) == {"ebird.fct_daily_bird_observations"}


def test_ack_from_pr_body_multiple() -> None:
    body = (
        "Dropping two columns intentionally:\n"
        "accept-breaking-change: ebird.fct_daily_bird_observations\n"
        "accept-breaking-change: noaa.fct_daily_weather\n"
    )
    assert acknowledgements(body, None) == {
        "ebird.fct_daily_bird_observations",
        "noaa.fct_daily_weather",
    }


def test_ack_env_and_pr_body_merge() -> None:
    body = "accept-breaking-change: model-a"
    assert acknowledgements(body, "model-b") == {"model-a", "model-b"}


def test_ack_none_when_neither_supplied() -> None:
    assert acknowledgements(None, None) == set()
