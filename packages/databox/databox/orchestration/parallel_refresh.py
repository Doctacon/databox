"""Shared-server parallel Quack refresh orchestration."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import dagster as dg
from dagster import OpExecutionContext

from databox.config.settings import PROJECT_ROOT, settings
from databox.config.sources import SOURCES
from databox.destinations import QuackServer, cleanup_quack_clients, dedupe_quack_raw_tables

_SHARED_SERVER_ENV = "DATABOX_QUACK_SHARED_SERVER"
_TIMELINE_DIR_ENV = "DATABOX_QUACK_TIMELINE_DIR"


@dataclass(frozen=True)
class SourceRunResult:
    source: str
    returncode: int
    started_monotonic: float
    finished_monotonic: float
    started_at: str
    finished_at: str
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class WarehouseInspection:
    row_counts: tuple[tuple[str, int], ...]
    main_dlt_relations: tuple[str, ...]


@dataclass(frozen=True)
class ParallelRefreshResult:
    sources: tuple[SourceRunResult, ...]
    deduped: tuple[str, ...]
    inspection: WarehouseInspection

    @property
    def overlap_pairs(self) -> tuple[tuple[str, str], ...]:
        pairs: list[tuple[str, str]] = []
        for index, left in enumerate(self.sources):
            for right in self.sources[index + 1 :]:
                if (
                    left.started_monotonic < right.finished_monotonic
                    and right.started_monotonic < left.finished_monotonic
                ):
                    pairs.append((left.source, right.source))
        return tuple(pairs)


class ParallelRefreshError(RuntimeError):
    def __init__(self, result: ParallelRefreshResult) -> None:
        self.result = result
        failures = [
            f"{item.source}: {item.message or item.returncode}"
            for item in result.sources
            if not item.ok
        ]
        super().__init__("Source refresh failed: " + "; ".join(failures))


SourceRunner = Callable[[str, Path, Mapping[str, str]], SourceRunResult]
ServerFactory = Callable[[str], QuackServer]
DedupeRunner = Callable[[str], list[str]]
TransformRunner = Callable[[], None]
CleanupRunner = Callable[[], None]
InspectionRunner = Callable[[str, Sequence[str]], WarehouseInspection]
EvaluationRunner = Callable[[str, str], object]


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _dagster_command(source: str) -> list[str]:
    dg_path = shutil.which("dg") or str(Path(sys.executable).with_name("dg"))
    return [
        dg_path,
        "launch",
        "--target-path",
        str(PROJECT_ROOT / "packages" / "databox"),
        "--job",
        f"{source}_ingest",
    ]


class IngestTimeline(TypedDict):
    started_monotonic: float
    finished_monotonic: float
    started_at: str
    finished_at: str


def _read_ingest_timeline(source: str, env: Mapping[str, str]) -> IngestTimeline | None:
    timeline_dir = env.get(_TIMELINE_DIR_ENV)
    if not timeline_dir:
        return None
    path = Path(timeline_dir) / f"raw_{source}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    started = float(payload["started_monotonic"])
    finished = float(payload["finished_monotonic"])
    if finished < started:
        raise ValueError(f"Invalid ingest timeline for {source}")
    return IngestTimeline(
        started_monotonic=started,
        finished_monotonic=finished,
        started_at=str(payload["started_at"]),
        finished_at=str(payload["finished_at"]),
    )


def run_source_dagster_job(
    source: str,
    workdir: Path,
    env: Mapping[str, str],
) -> SourceRunResult:
    """Launch one Dagster source job and report its actual ingest-session interval."""
    process_started = time.monotonic()
    process_started_at = _iso_now()
    print(f"SOURCE_START source={source} at={process_started_at}", flush=True)
    try:
        completed = subprocess.run(
            _dagster_command(source),
            cwd=workdir,
            env=dict(env),
            check=False,
        )
        returncode = completed.returncode
        message = "completed" if returncode == 0 else f"Dagster exit code {returncode}"
    except Exception as exc:  # noqa: BLE001 - normalize worker failure for the orchestrator
        returncode = 1
        message = f"{type(exc).__name__}: {exc}"
    process_finished = time.monotonic()
    process_finished_at = _iso_now()

    try:
        timeline = _read_ingest_timeline(source, env)
    except Exception as exc:  # noqa: BLE001 - malformed evidence fails the source
        timeline = None
        returncode = 1
        message = f"Invalid ingest timeline: {type(exc).__name__}: {exc}"
    if timeline is None:
        if returncode == 0:
            returncode = 1
            message = "Dagster succeeded without an ingest timeline"
        started_monotonic = process_started
        finished_monotonic = process_started
        started_at = process_started_at
        finished_at = process_started_at
    else:
        started_monotonic = timeline["started_monotonic"]
        finished_monotonic = timeline["finished_monotonic"]
        started_at = str(timeline["started_at"])
        finished_at = str(timeline["finished_at"])

    print(
        f"SOURCE_END source={source} at={process_finished_at} status={returncode} "
        f"process_seconds={process_finished - process_started:.3f} "
        f"ingest_seconds={finished_monotonic - started_monotonic:.3f}",
        flush=True,
    )
    return SourceRunResult(
        source=source,
        returncode=returncode,
        started_monotonic=started_monotonic,
        finished_monotonic=finished_monotonic,
        started_at=started_at,
        finished_at=finished_at,
        message=message,
    )


def run_sqlmesh_prod() -> None:
    subprocess.run([str(PROJECT_ROOT / "scripts" / "sqlmesh_plan_prod.sh")], check=True)


def inspect_refresh_state(database_path: str, source_names: Sequence[str]) -> WarehouseInspection:
    import duckdb

    source_by_name = {source.name: source for source in SOURCES}
    con = duckdb.connect(database_path, read_only=True)
    try:
        row_counts: list[tuple[str, int]] = []
        for source_name in source_names:
            source = source_by_name[source_name]
            for table in source.raw_tables:
                qualified = f"raw_{source_name}.{table}"
                row = con.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()
                row_counts.append((qualified, int(row[0]) if row else 0))
        main_dlt = tuple(
            str(row[0])
            for row in con.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main' AND table_name LIKE '\\_dlt%' ESCAPE '\\'
                ORDER BY table_name
                """
            ).fetchall()
        )
    finally:
        con.close()
    if main_dlt:
        raise RuntimeError(f"Persistent main._dlt relations found: {', '.join(main_dlt)}")
    return WarehouseInspection(row_counts=tuple(row_counts), main_dlt_relations=main_dlt)


def _default_server_factory(database_path: str) -> QuackServer:
    return QuackServer(db_path=database_path)


def _shared_client_environment(timeline_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env[_SHARED_SERVER_ENV] = "true"
    env[_TIMELINE_DIR_ENV] = str(timeline_dir)
    env.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
    env.setdefault("SQLMESH__DISABLE_ANONYMIZED_ANALYTICS", "true")
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (f":{python_path}" if python_path else "")
    venv_bin = str(Path(sys.executable).parent)
    env.setdefault("VIRTUAL_ENV", str(Path(venv_bin).parent))
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    return env


def execute_parallel_refresh(
    source_names: Sequence[str] | None = None,
    *,
    database_path: str | None = None,
    max_workers: int | None = None,
    source_runner: SourceRunner = run_source_dagster_job,
    server_factory: ServerFactory = _default_server_factory,
    dedupe_runner: DedupeRunner = dedupe_quack_raw_tables,
    transform_runner: TransformRunner = run_sqlmesh_prod,
    cleanup_runner: CleanupRunner = cleanup_quack_clients,
    inspection_runner: InspectionRunner = inspect_refresh_state,
    run_transform: bool = True,
    evaluation_runner: EvaluationRunner | None = None,
) -> ParallelRefreshResult:
    """Run registered Dagster source jobs concurrently against one Quack server."""
    eligible_sources = [source for source in SOURCES if source.parallel_refresh]
    names = list(source_names or [source.name for source in eligible_sources])
    if not names:
        raise ValueError("At least one source is required")
    if len(set(names)) != len(names):
        raise ValueError("Source names must be unique")
    known = {source.name for source in eligible_sources}
    unknown = sorted(set(names) - known)
    if unknown:
        raise ValueError(f"Unknown sources: {', '.join(unknown)}")

    worker_count = max_workers or len(names)
    if worker_count < 1:
        raise ValueError("max_workers must be positive")
    if len(names) > 1 and worker_count < 2:
        raise ValueError("Parallel refresh requires at least two workers")

    target = database_path or settings.database_path
    results_by_name: dict[str, SourceRunResult] = {}
    deduped: list[str] = []
    post_errors: list[BaseException] = []
    server_started = False

    try:
        with tempfile.TemporaryDirectory(prefix="databox-parallel-refresh-") as temp_dir:
            work_root = Path(temp_dir)
            timeline_dir = work_root / "timelines"
            timeline_dir.mkdir()
            env = _shared_client_environment(timeline_dir)
            with server_factory(target):
                server_started = True
                with ThreadPoolExecutor(max_workers=worker_count) as pool:
                    future_sources = {}
                    for name in names:
                        workdir = work_root / name
                        workdir.mkdir()
                        future = pool.submit(source_runner, name, workdir, env)
                        future_sources[future] = name
                    for future in as_completed(future_sources):
                        name = future_sources[future]
                        try:
                            results_by_name[name] = future.result()
                        except Exception as exc:  # noqa: BLE001 - preserve all peer results
                            now = time.monotonic()
                            timestamp = _iso_now()
                            results_by_name[name] = SourceRunResult(
                                source=name,
                                returncode=1,
                                started_monotonic=now,
                                finished_monotonic=now,
                                started_at=timestamp,
                                finished_at=timestamp,
                                message=f"{type(exc).__name__}: {exc}",
                            )
    finally:
        if server_started:
            try:
                deduped = dedupe_runner(target)
            except BaseException as exc:  # noqa: BLE001 - preserve source failures
                post_errors.append(exc)
        try:
            cleanup_runner()
        except BaseException as exc:  # noqa: BLE001 - preserve source failures
            post_errors.append(exc)

    ordered_results = tuple(results_by_name[name] for name in names)
    empty_inspection = WarehouseInspection(row_counts=(), main_dlt_relations=())
    result = ParallelRefreshResult(
        sources=ordered_results,
        deduped=tuple(deduped),
        inspection=empty_inspection,
    )
    failures = [source for source in result.sources if not source.ok]
    if failures:
        error = ParallelRefreshError(result)
        for post_error in post_errors:
            error.add_note(f"Post-refresh error: {type(post_error).__name__}: {post_error}")
        if post_errors:
            raise error from post_errors[0]
        raise error
    if post_errors:
        details = "; ".join(f"{type(exc).__name__}: {exc}" for exc in post_errors)
        raise RuntimeError(f"Post-refresh maintenance failed: {details}") from post_errors[0]
    if len(names) > 1 and not result.overlap_pairs:
        raise RuntimeError("Source ingest sessions completed without an observed overlap interval")

    inspection = inspection_runner(target, names)
    result = ParallelRefreshResult(
        sources=ordered_results,
        deduped=tuple(deduped),
        inspection=inspection,
    )
    if run_transform:
        print("PHASE_START phase=sqlmesh", flush=True)
        transform_runner()
        if evaluation_runner is not None:
            refresh_payload = [
                {
                    "source": item.source,
                    "started_at": item.started_at,
                    "finished_at": item.finished_at,
                }
                for item in result.sources
            ]
            refresh_id = (
                "parallel_refresh_"
                + hashlib.sha256(
                    json.dumps(refresh_payload, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
            )
            evaluation_runner(target, refresh_id)
    return result


@dg.op(name="parallel_quack_refresh")
def parallel_quack_refresh_op(context: OpExecutionContext) -> None:
    from databox.watched_bird_evaluator import run_watched_bird_evaluator

    result = execute_parallel_refresh(evaluation_runner=run_watched_bird_evaluator)
    context.log.info(
        "parallel Quack refresh complete: sources=%s overlap_pairs=%s deduped=%s",
        [item.source for item in result.sources],
        result.overlap_pairs,
        result.deduped,
    )


@dg.job(name="parallel_quack_full_refresh", executor_def=dg.in_process_executor)
def parallel_quack_full_refresh() -> None:
    parallel_quack_refresh_op()


parallel_quack_schedule = dg.ScheduleDefinition(
    job=parallel_quack_full_refresh,
    cron_schedule="0 6 * * *",
)
