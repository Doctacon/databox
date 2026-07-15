"""Shared-server parallel Quack refresh orchestration tests."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import duckdb
import pytest
from databox.orchestration.parallel_refresh import (
    ParallelRefreshError,
    SourceRunResult,
    WarehouseInspection,
    execute_parallel_refresh,
    inspect_refresh_state,
    run_source_dagster_job,
)


def _result(source: str, start: float, end: float, returncode: int = 0) -> SourceRunResult:
    return SourceRunResult(
        source=source,
        returncode=returncode,
        started_monotonic=start,
        finished_monotonic=end,
        started_at="2026-07-09T00:00:00+00:00",
        finished_at="2026-07-09T00:00:01+00:00",
        message="completed" if returncode == 0 else "failed",
    )


def test_parallel_refresh_uses_one_server_observes_overlap_then_transforms(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    barrier = threading.Barrier(3)
    seen_environments: list[dict[str, str]] = []

    class FakeServer:
        def __enter__(self) -> None:
            events.append("server-start")

        def __exit__(self, *args: Any) -> None:
            events.append("server-stop")

    def server_factory(database_path: str) -> FakeServer:
        assert database_path == str(tmp_path / "databox.duckdb")
        events.append("server-create")
        return FakeServer()

    def source_runner(source: str, workdir: Path, env: dict[str, str]) -> SourceRunResult:
        assert workdir.name == source
        seen_environments.append(dict(env))
        barrier.wait(timeout=2)
        start = time.monotonic()
        events.append(f"source-start:{source}")
        time.sleep(0.03)
        end = time.monotonic()
        events.append(f"source-end:{source}")
        return _result(source, start, end)

    def dedupe(database_path: str) -> list[str]:
        assert events.index("server-stop") < len(events)
        events.append("dedupe")
        return ["raw_ebird.recent_observations: 2 -> 1"]

    def transform() -> None:
        events.append("transform")

    result = execute_parallel_refresh(
        ["ebird", "gbif", "usgs_earthquakes"],
        database_path=str(tmp_path / "databox.duckdb"),
        source_runner=source_runner,
        server_factory=server_factory,
        dedupe_runner=dedupe,
        transform_runner=transform,
        cleanup_runner=lambda: events.append("cleanup"),
        inspection_runner=lambda *_: WarehouseInspection(
            row_counts=(("raw_ebird.recent_observations", 1),),
            main_dlt_relations=(),
        ),
        evaluation_runner=lambda path, refresh_id: events.append(f"evaluate:{path}:{refresh_id}"),
    )

    assert events.count("server-start") == 1
    assert events.count("server-stop") == 1
    assert events.index("server-stop") < events.index("dedupe")
    assert events.index("dedupe") < events.index("transform")
    assert events.index("cleanup") < events.index("transform")
    evaluation_event = next(item for item in events if item.startswith("evaluate:"))
    assert events.index("transform") < events.index(evaluation_event)
    assert evaluation_event.startswith(f"evaluate:{tmp_path / 'databox.duckdb'}:parallel_refresh_")
    assert result.overlap_pairs
    assert result.deduped == ("raw_ebird.recent_observations: 2 -> 1",)
    assert all(env["DATABOX_QUACK_SHARED_SERVER"] == "true" for env in seen_environments)


def test_parallel_refresh_failure_preserves_source_attribution_when_maintenance_fails(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    barrier = threading.Barrier(2)

    class FakeServer:
        def __enter__(self) -> None:
            events.append("server-start")

        def __exit__(self, *args: Any) -> None:
            events.append("server-stop")

    def source_runner(source: str, workdir: Path, env: dict[str, str]) -> SourceRunResult:
        _ = workdir, env
        barrier.wait(timeout=2)
        start = time.monotonic()
        time.sleep(0.02)
        return _result(source, start, time.monotonic(), returncode=1 if source == "gbif" else 0)

    def failing_dedupe(_: str) -> list[str]:
        events.append("dedupe")
        raise RuntimeError("dedupe failed")

    def failing_cleanup() -> None:
        events.append("cleanup")
        raise RuntimeError("cleanup failed")

    with pytest.raises(ParallelRefreshError, match="gbif: failed") as exc_info:
        execute_parallel_refresh(
            ["gbif", "usgs_earthquakes"],
            database_path=str(tmp_path / "databox.duckdb"),
            source_runner=source_runner,
            server_factory=lambda _: FakeServer(),
            dedupe_runner=failing_dedupe,
            transform_runner=lambda: events.append("transform"),
            cleanup_runner=failing_cleanup,
            evaluation_runner=lambda *_: events.append("evaluate"),
        )

    assert [item.source for item in exc_info.value.result.sources if not item.ok] == ["gbif"]
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert any("cleanup failed" in note for note in exc_info.value.__notes__)
    assert events == ["server-start", "server-stop", "dedupe", "cleanup"]


def test_dagster_runner_uses_actual_ingest_timeline(tmp_path: Path, monkeypatch) -> None:
    timeline_dir = tmp_path / "timelines"
    timeline_dir.mkdir()
    env = {"DATABOX_QUACK_TIMELINE_DIR": str(timeline_dir)}

    def fake_run(command, *, cwd, env, check):
        _ = cwd, check
        (Path(env["DATABOX_QUACK_TIMELINE_DIR"]) / "raw_ebird.json").write_text(
            json.dumps(
                {
                    "started_monotonic": 20.0,
                    "finished_monotonic": 21.5,
                    "started_at": "start",
                    "finished_at": "finish",
                }
            )
        )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_source_dagster_job("ebird", tmp_path, env)

    assert (result.started_monotonic, result.finished_monotonic) == (20.0, 21.5)
    assert (result.started_at, result.finished_at) == ("start", "finish")


def test_parallel_gate_rejects_nonoverlapping_ingest_intervals(tmp_path: Path) -> None:
    intervals = {"gbif": (1.0, 2.0), "usgs_earthquakes": (3.0, 4.0)}

    class FakeServer:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: Any) -> None:
            return None

    def source_runner(source: str, workdir: Path, env: dict[str, str]) -> SourceRunResult:
        _ = workdir, env
        start, end = intervals[source]
        return _result(source, start, end)

    with pytest.raises(RuntimeError, match="ingest sessions"):
        execute_parallel_refresh(
            list(intervals),
            database_path=str(tmp_path / "databox.duckdb"),
            source_runner=source_runner,
            server_factory=lambda _: FakeServer(),
            dedupe_runner=lambda _: [],
            cleanup_runner=lambda: None,
            inspection_runner=lambda *_: WarehouseInspection((), ()),
            run_transform=False,
        )


def test_evaluator_failure_propagates_only_after_successful_transform(tmp_path: Path) -> None:
    events: list[str] = []

    class FakeServer:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: Any) -> None:
            return None

    def source_runner(source: str, workdir: Path, env: dict[str, str]) -> SourceRunResult:
        _ = workdir, env
        return _result(source, 1.0, 2.0)

    def fail_evaluation(*_: str) -> None:
        events.append("evaluate")
        raise RuntimeError("evaluation failed")

    with pytest.raises(RuntimeError, match="evaluation failed"):
        execute_parallel_refresh(
            ["ebird"],
            database_path=str(tmp_path / "databox.duckdb"),
            source_runner=source_runner,
            server_factory=lambda _: FakeServer(),
            dedupe_runner=lambda _: [],
            cleanup_runner=lambda: None,
            inspection_runner=lambda *_: WarehouseInspection((), ()),
            transform_runner=lambda: events.append("transform"),
            evaluation_runner=fail_evaluation,
        )
    assert events == ["transform", "evaluate"]


def test_transform_failure_never_evaluates_watches(tmp_path: Path) -> None:
    events: list[str] = []

    class FakeServer:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: Any) -> None:
            return None

    def source_runner(source: str, workdir: Path, env: dict[str, str]) -> SourceRunResult:
        _ = workdir, env
        return _result(source, 1.0, 2.0)

    def fail_transform() -> None:
        events.append("transform")
        raise RuntimeError("transform failed")

    with pytest.raises(RuntimeError, match="transform failed"):
        execute_parallel_refresh(
            ["ebird"],
            database_path=str(tmp_path / "databox.duckdb"),
            source_runner=source_runner,
            server_factory=lambda _: FakeServer(),
            dedupe_runner=lambda _: [],
            cleanup_runner=lambda: None,
            inspection_runner=lambda *_: WarehouseInspection((), ()),
            transform_runner=fail_transform,
            evaluation_runner=lambda *_: events.append("evaluate"),
        )
    assert events == ["transform"]


def test_parallel_refresh_rejects_sequential_worker_count() -> None:
    with pytest.raises(ValueError, match="at least two workers"):
        execute_parallel_refresh(
            ["gbif", "usgs_earthquakes"],
            max_workers=1,
            run_transform=False,
        )


def test_refresh_inspection_reports_rows_and_rejects_main_dlt(tmp_path: Path) -> None:
    db_path = tmp_path / "databox.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA raw_gbif")
    con.execute("CREATE TABLE raw_gbif.occurrences (id INTEGER)")
    con.execute("INSERT INTO raw_gbif.occurrences VALUES (1), (2)")
    con.close()

    inspection = inspect_refresh_state(str(db_path), ["gbif"])
    assert inspection.row_counts == (("raw_gbif.occurrences", 2),)
    assert inspection.main_dlt_relations == ()

    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE main._dlt_bad (id INTEGER)")
    con.close()
    with pytest.raises(RuntimeError, match="Persistent main._dlt"):
        inspect_refresh_state(str(db_path), ["gbif"])


def test_refresh_inspection_uses_complete_ebird_and_noaa_inventories(tmp_path: Path) -> None:
    db_path = tmp_path / "databox.duckdb"
    tables = {
        "ebird": (
            "recent_observations",
            "notable_observations",
            "hotspots",
            "species_list",
            "taxonomy",
            "region_stats",
        ),
        "noaa": ("daily_weather", "stations", "datasets"),
    }
    con = duckdb.connect(str(db_path))
    for source, source_tables in tables.items():
        con.execute(f"CREATE SCHEMA raw_{source}")
        for table in source_tables:
            con.execute(f"CREATE TABLE raw_{source}.{table} (id INTEGER)")
            con.execute(f"INSERT INTO raw_{source}.{table} VALUES (1)")
    con.close()

    inspection = inspect_refresh_state(str(db_path), ["ebird", "noaa"])
    assert inspection.row_counts == tuple(
        (f"raw_{source}.{table}", 1)
        for source, source_tables in tables.items()
        for table in source_tables
    )


def test_parallel_refresh_job_is_available_in_dagster_definitions() -> None:
    from databox.orchestration.definitions import defs

    assert defs.get_job_def("parallel_quack_full_refresh").name == "parallel_quack_full_refresh"
    expected_schedules = {
        "ebird_daily_pipeline_schedule",
        "gbif_daily_pipeline_schedule",
        "xeno_canto_daily_pipeline_schedule",
        "noaa_daily_pipeline_schedule",
        "usgs_daily_pipeline_schedule",
        "usgs_earthquakes_daily_pipeline_schedule",
        "parallel_quack_full_refresh_schedule",
    }
    schedule_names = {schedule.name for schedule in defs.get_repository_def().schedule_defs}
    assert schedule_names == expected_schedules
