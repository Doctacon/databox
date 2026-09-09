"""Parallel Polaris Iceberg refresh orchestration tests."""

from __future__ import annotations

import subprocess
import threading
import time
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from databox.config.sources import SOURCES
from databox.orchestration.parallel_refresh import (
    ParallelRefreshError,
    SourceRunResult,
    WarehouseInspection,
    execute_parallel_refresh,
    inspect_refresh_state,
    run_source_dagster_job,
)


def test_parallel_source_jobs_select_only_dlt_ingestion_assets() -> None:
    for source in SOURCES:
        if not source.parallel_refresh:
            continue
        module = import_module(source.domain_module)
        selection = str(module.ingest_job.selection)
        assert all(key.to_user_string() in selection for key in module.dlt_asset_keys)
        assert getattr(module, f"{source.name}_load_status_key").to_user_string() in selection
        assert all(key.to_user_string() not in selection for key in module.sqlmesh_asset_keys)


def _skip_real_iceberg_preflight() -> None:
    """Fake-runner tests exercise orchestration, not live publication configuration."""


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


def test_parallel_refresh_observes_overlap_then_transforms(
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
        preflight_runner=_skip_real_iceberg_preflight,
    )

    assert "server-start" not in events
    assert "server-stop" not in events
    assert "dedupe" not in events
    assert "cleanup" not in events
    evaluation_event = next(item for item in events if item.startswith("evaluate:"))
    assert events.index("transform") < events.index(evaluation_event)
    assert evaluation_event.startswith(f"evaluate:{tmp_path / 'databox.duckdb'}:parallel_refresh_")
    assert result.overlap_pairs
    assert result.deduped == ()
    assert all("DATABOX_QUACK_SHARED_SERVER" not in env for env in seen_environments)


def test_parallel_source_imports_use_isolated_sqlmesh_caches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_cache_dirs: dict[str, Path] = {}
    barrier = threading.Barrier(2)
    monkeypatch.setenv("SQLMESH__CACHE_DIR", "/shared/sqlmesh-cache")

    class FakeServer:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: Any) -> None:
            return None

    def source_runner(source: str, workdir: Path, env: dict[str, str]) -> SourceRunResult:
        cache_dir = Path(env["SQLMESH__CACHE_DIR"])
        seen_cache_dirs[source] = cache_dir
        assert cache_dir == workdir / "sqlmesh-cache"
        barrier.wait(timeout=2)
        return _result(source, 1.0, 2.0)

    execute_parallel_refresh(
        ["gbif", "usgs_earthquakes"],
        database_path=str(tmp_path / "databox.duckdb"),
        source_runner=source_runner,
        server_factory=lambda _: FakeServer(),
        dedupe_runner=lambda _: [],
        cleanup_runner=lambda: None,
        inspection_runner=lambda *_: WarehouseInspection((), ()),
        run_transform=False,
        preflight_runner=_skip_real_iceberg_preflight,
    )

    assert set(seen_cache_dirs) == {"gbif", "usgs_earthquakes"}
    assert len(set(seen_cache_dirs.values())) == 2
    assert all(path.is_absolute() for path in seen_cache_dirs.values())
    assert all(path != Path("/shared/sqlmesh-cache") for path in seen_cache_dirs.values())


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
            preflight_runner=_skip_real_iceberg_preflight,
        )

    assert [item.source for item in exc_info.value.result.sources if not item.ok] == ["gbif"]
    assert exc_info.value.__cause__ is None
    assert events == []


def test_dagster_runner_uses_worker_process_timeline(tmp_path: Path, monkeypatch) -> None:
    moments = iter([20.0, 21.5])
    timestamps = iter(["start", "finish"])

    def fake_run(command, *, cwd, env, check):
        _ = cwd, env, check
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        "databox.orchestration.parallel_refresh.time.monotonic",
        lambda: next(moments),
    )
    monkeypatch.setattr(
        "databox.orchestration.parallel_refresh._iso_now",
        lambda: next(timestamps),
    )
    result = run_source_dagster_job("ebird", tmp_path, {})

    assert result.ok
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
            preflight_runner=_skip_real_iceberg_preflight,
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
            preflight_runner=_skip_real_iceberg_preflight,
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
            preflight_runner=_skip_real_iceberg_preflight,
        )
    assert events == ["transform"]


def test_parallel_refresh_stops_before_source_execution_when_preflight_fails(
    tmp_path: Path,
) -> None:
    sources_started: list[str] = []

    def source_runner(source: str, *_: object) -> SourceRunResult:
        sources_started.append(source)
        raise AssertionError("source runner must not execute after failed preflight")

    def failing_preflight() -> None:
        raise ValueError("AWS writer credentials")

    with pytest.raises(ValueError, match="AWS writer credentials"):
        execute_parallel_refresh(
            ["ebird"],
            database_path=str(tmp_path / "databox.duckdb"),
            source_runner=source_runner,
            preflight_runner=failing_preflight,
        )

    assert sources_started == []


def test_parallel_refresh_rejects_sequential_worker_count() -> None:
    with pytest.raises(ValueError, match="at least two workers"):
        execute_parallel_refresh(
            ["gbif", "usgs_earthquakes"],
            max_workers=1,
            run_transform=False,
        )


class _FakeScan:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class _FakeTable:
    def __init__(self, count: int) -> None:
        self._count = count

    def scan(self) -> _FakeScan:
        return _FakeScan(self._count)


class _FakeCatalog:
    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts

    def load_table(self, name: str) -> _FakeTable:
        return _FakeTable(self._counts[name])


def test_refresh_inspection_reports_iceberg_rows_and_requires_load_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from databox.orchestration import parallel_refresh

    counts = {"raw_gbif.occurrences": 2, "raw_gbif._dlt_load_status": 1}
    monkeypatch.setattr(
        type(parallel_refresh.settings),
        "pyiceberg_catalog",
        lambda _settings: _FakeCatalog(counts),
    )
    inspection = inspect_refresh_state(str(tmp_path / "databox.duckdb"), ["gbif"])
    assert inspection.row_counts == (("raw_gbif.occurrences", 2),)
    assert inspection.main_dlt_relations == ()

    counts["raw_gbif._dlt_load_status"] = 0
    with pytest.raises(RuntimeError, match="No completed Iceberg load status found for gbif"):
        inspect_refresh_state(str(tmp_path / "databox.duckdb"), ["gbif"])


def test_refresh_inspection_uses_complete_ebird_and_noaa_inventories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from databox.orchestration import parallel_refresh

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
    counts = {
        f"raw_{source}.{table}": 1
        for source, source_tables in tables.items()
        for table in source_tables
    }
    counts.update({f"raw_{source}._dlt_load_status": 1 for source in tables})
    monkeypatch.setattr(
        type(parallel_refresh.settings),
        "pyiceberg_catalog",
        lambda _settings: _FakeCatalog(counts),
    )

    inspection = inspect_refresh_state(str(tmp_path / "databox.duckdb"), ["ebird", "noaa"])
    assert inspection.row_counts == tuple(
        (f"raw_{source}.{table}", 1)
        for source, source_tables in tables.items()
        for table in source_tables
    )


def test_parallel_refresh_job_is_available_in_dagster_definitions() -> None:
    from databox.orchestration.definitions import defs

    assert defs.get_job_def("parallel_iceberg_full_refresh").name == "parallel_iceberg_full_refresh"
    expected_schedules = {
        "ebird_daily_pipeline_schedule",
        "gbif_daily_pipeline_schedule",
        "xeno_canto_daily_pipeline_schedule",
        "noaa_daily_pipeline_schedule",
        "usgs_daily_pipeline_schedule",
        "usgs_earthquakes_daily_pipeline_schedule",
        "parallel_iceberg_full_refresh_schedule",
    }
    schedule_names = {schedule.name for schedule in defs.get_repository_def().schedule_defs}
    assert schedule_names == expected_schedules
