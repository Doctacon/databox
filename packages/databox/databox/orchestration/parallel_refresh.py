"""Parallel refresh orchestration for Polaris-authoritative Iceberg sources."""

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

import dagster as dg
from dagster import OpExecutionContext

from databox.config.settings import PROJECT_ROOT, settings
from databox.config.sources import SOURCES

_SQLMESH_CACHE_DIR_ENV = "SQLMESH__CACHE_DIR"


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
TransformRunner = Callable[[], None]
InspectionRunner = Callable[[str, Sequence[str]], WarehouseInspection]
PreflightRunner = Callable[[], None]
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


def run_source_dagster_job(
    source: str,
    workdir: Path,
    env: Mapping[str, str],
) -> SourceRunResult:
    """Launch one Dagster source job and report its worker-process interval."""
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

    print(
        f"SOURCE_END source={source} at={process_finished_at} status={returncode} "
        f"process_seconds={process_finished - process_started:.3f}",
        flush=True,
    )
    return SourceRunResult(
        source=source,
        returncode=returncode,
        started_monotonic=process_started,
        finished_monotonic=process_finished,
        started_at=process_started_at,
        finished_at=process_finished_at,
        message=message,
    )


def run_sqlmesh_prod() -> None:
    subprocess.run(
        [str(PROJECT_ROOT / "scripts" / "analytics" / "sqlmesh_plan_prod.sh")], check=True
    )


def validate_iceberg_refresh_config() -> None:
    """Fail before workers start when Polaris or S3 writer config is unavailable."""
    if not settings.aws_s3_bucket:
        raise ValueError("DATABOX_AWS_S3_BUCKET is required for Iceberg refresh")
    if (
        not settings.aws_access_key_id.get_secret_value()
        or not settings.aws_secret_access_key.get_secret_value()
    ):
        raise ValueError("AWS writer credentials are required for Iceberg refresh")
    settings.pyiceberg_catalog()


def inspect_refresh_state(_database_path: str, source_names: Sequence[str]) -> WarehouseInspection:
    """Count authoritative Iceberg tables and require explicit load status."""
    source_by_name = {source.name: source for source in SOURCES}
    catalog = settings.pyiceberg_catalog()
    row_counts: list[tuple[str, int]] = []
    for source_name in source_names:
        source = source_by_name[source_name]
        dataset = f"raw_{source_name}"
        for table_name in source.raw_tables:
            qualified = f"{dataset}.{table_name}"
            row_counts.append((qualified, catalog.load_table(qualified).scan().count()))
        status_count = catalog.load_table(f"{dataset}._dlt_load_status").scan().count()
        if status_count < 1:
            raise RuntimeError(f"No completed Iceberg load status found for {source_name}")
    return WarehouseInspection(row_counts=tuple(row_counts), main_dlt_relations=())


def _shared_client_environment() -> dict[str, str]:
    env = os.environ.copy()
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
    server_factory: object | None = None,
    dedupe_runner: object | None = None,
    cleanup_runner: object | None = None,
    transform_runner: TransformRunner = run_sqlmesh_prod,
    inspection_runner: InspectionRunner = inspect_refresh_state,
    preflight_runner: PreflightRunner = validate_iceberg_refresh_config,
    run_transform: bool = True,
    evaluation_runner: EvaluationRunner | None = None,
) -> ParallelRefreshResult:
    """Run registered Dagster source jobs concurrently against Polaris Iceberg."""
    _ = server_factory, dedupe_runner, cleanup_runner  # Removed Quack compatibility kwargs.
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
    preflight_runner()
    results_by_name: dict[str, SourceRunResult] = {}
    with tempfile.TemporaryDirectory(prefix="databox-parallel-refresh-") as temp_dir:
        work_root = Path(temp_dir)
        env = _shared_client_environment()
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            future_sources = {}
            for name in names:
                workdir = work_root / name
                workdir.mkdir()
                source_env = dict(env)
                source_env[_SQLMESH_CACHE_DIR_ENV] = str(workdir / "sqlmesh-cache")
                future_sources[pool.submit(source_runner, name, workdir, source_env)] = name
            for future in as_completed(future_sources):
                name = future_sources[future]
                try:
                    results_by_name[name] = future.result()
                except Exception as exc:  # noqa: BLE001
                    now = time.monotonic()
                    timestamp = _iso_now()
                    results_by_name[name] = SourceRunResult(
                        name,
                        1,
                        now,
                        now,
                        timestamp,
                        timestamp,
                        f"{type(exc).__name__}: {exc}",
                    )

    ordered_results = tuple(results_by_name[name] for name in names)
    empty_inspection = WarehouseInspection(row_counts=(), main_dlt_relations=())
    result = ParallelRefreshResult(
        sources=ordered_results,
        deduped=(),
        inspection=empty_inspection,
    )
    failures = [source for source in result.sources if not source.ok]
    if failures:
        raise ParallelRefreshError(result)
    if len(names) > 1 and not result.overlap_pairs:
        raise RuntimeError("Source ingest sessions completed without an observed overlap interval")

    inspection = inspection_runner(target, names)
    result = ParallelRefreshResult(
        sources=ordered_results,
        deduped=(),
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


@dg.op(name="parallel_iceberg_refresh")
def parallel_iceberg_refresh_op(context: OpExecutionContext) -> None:
    result = execute_parallel_refresh()
    context.log.info(
        "parallel Iceberg refresh complete: sources=%s overlap_pairs=%s deduped=%s",
        [item.source for item in result.sources],
        result.overlap_pairs,
        result.deduped,
    )


@dg.job(name="parallel_iceberg_full_refresh", executor_def=dg.in_process_executor)
def parallel_iceberg_full_refresh() -> None:
    parallel_iceberg_refresh_op()


parallel_iceberg_schedule = dg.ScheduleDefinition(
    job=parallel_iceberg_full_refresh,
    cron_schedule="0 6 * * *",
)
