"""Shared Dagster wiring primitives — used by every domain module.

Anything that is cross-domain (the single SQLMesh multi-asset, dlt and
Soda factory helpers, the SQLMesh translator, the freshness policy
applier) lives here. Domain modules compose these primitives without
knowing about each other.
"""

import logging
import typing as t
from datetime import UTC, timedelta
from pathlib import Path

import dagster as dg
import dlt
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltTranslator
from dagster_dlt.translator import DltResourceTranslatorData
from dagster_sqlmesh import SQLMeshContextConfig, SQLMeshResource, sqlmesh_assets
from dagster_sqlmesh.translator import SQLMeshDagsterTranslator
from sqlglot import exp

from databox.config.settings import PROJECT_ROOT, settings

log = logging.getLogger(__name__)

TRANSFORMS_DIR = PROJECT_ROOT / "transforms"
MAIN_TRANSFORM_PROJECT = TRANSFORMS_DIR / "main"
SODA_DIR = PROJECT_ROOT / "soda"


class DataboxSQLMeshTranslator(SQLMeshDagsterTranslator):
    def get_asset_key_name(self, fqn: str) -> t.Sequence[str]:
        table = exp.to_table(fqn)
        # Three-part FQN for attached raw catalogs (e.g., raw_ebird.main.table):
        # catalog IS the meaningful namespace; "main" is just the default schema.
        if table.catalog and str(table.db) == "main" and str(table.catalog).startswith("raw_"):
            return ["sqlmesh", str(table.catalog), table.name]
        return ["sqlmesh", table.db, table.name]


class DataboxSQLMeshContextConfig(SQLMeshContextConfig):
    def get_translator(self) -> SQLMeshDagsterTranslator:
        return DataboxSQLMeshTranslator()


class DataboxConfig(dg.ConfigurableResource):
    database_path: str = settings.database_path
    dlt_data_dir: str = settings.dlt_data_dir
    transforms_dir: str = str(TRANSFORMS_DIR)


_OPENLINEAGE_PRODUCER = "https://github.com/Doctacon/databox"


def _openlineage_emit_tick(
    context: dg.SensorEvaluationContext,
    client: t.Any,
    namespace: str,
    producer: str = _OPENLINEAGE_PRODUCER,
) -> dg.SensorResult:
    """Walk ASSET_MATERIALIZATION events since cursor, emit one OL RunEvent each.

    Pulled out of `openlineage_sensor_or_none()` so the emit logic is testable
    without instantiating a real Dagster sensor. The sensor closure is thin —
    it just calls this.
    """
    import uuid
    from datetime import datetime

    from openlineage.client.event_v2 import Job, OutputDataset, Run, RunEvent, RunState

    cursor = int(context.cursor) if context.cursor else 0
    records = context.instance.get_event_records(
        dg.EventRecordsFilter(
            event_type=dg.DagsterEventType.ASSET_MATERIALIZATION,
            after_cursor=cursor,
        ),
        limit=500,
        ascending=True,
    )
    latest_cursor = cursor
    for record in records:
        latest_cursor = max(latest_cursor, record.storage_id)
        event = record.event_log_entry.dagster_event
        if event is None or event.asset_key is None:
            continue
        name = event.asset_key.to_user_string()
        event_time = datetime.fromtimestamp(record.event_log_entry.timestamp, tz=UTC).isoformat()
        run_event = RunEvent(
            eventTime=event_time,
            producer=producer,
            run=Run(runId=str(uuid.uuid4())),
            job=Job(namespace=namespace, name=name),
            eventType=RunState.COMPLETE,
            inputs=[],
            outputs=[OutputDataset(namespace=namespace, name=name)],
        )
        try:
            client.emit(run_event)
        except Exception as exc:  # noqa: BLE001 — lineage failures must not kill Dagster
            context.log.warning(f"openlineage emit failed for {name}: {exc}")
    return dg.SensorResult(cursor=str(latest_cursor))


def openlineage_sensor_or_none() -> dg.SensorDefinition | None:
    """Return an OpenLineage-emitting sensor when OPENLINEAGE_URL is set.

    Walks Dagster's ASSET_MATERIALIZATION events and emits one OpenLineage
    RunEvent per materialization to whatever backend OPENLINEAGE_URL points
    at (Marquez / DataHub / OpenMetadata / Atlan / Astro). OPENLINEAGE_URL,
    OPENLINEAGE_NAMESPACE, and OPENLINEAGE_API_KEY are mirrored in
    `DataboxSettings` so `.env` is the one place forkers configure them.

    Ships disabled by default: no URL, no sensor, no import cost. Forker
    drops OPENLINEAGE_URL=http://marquez:5000 in .env, restarts Dagster,
    lineage starts flowing.

    Installation: `uv sync --package databox --extra lineage`. Missing
    install returns None with a warning so the stack stays bootable.

    The upstream `openlineage-dagster` package is not used — it pins
    Dagster <=1.6.9, which conflicts with dagster-sqlmesh's >=1.7.8 floor.
    We emit via `openlineage-python` directly.
    """
    if not settings.openlineage_url:
        return None
    try:
        from openlineage.client import OpenLineageClient
        from openlineage.client.transport.http import (
            ApiKeyTokenProvider,
            HttpConfig,
            HttpTransport,
        )
    except ImportError:
        log.warning(
            "OPENLINEAGE_URL is set but openlineage-python is not installed. "
            "Run `uv sync --package databox --extra lineage` to enable "
            "lineage emission."
        )
        return None

    http_kwargs: dict[str, t.Any] = {"url": settings.openlineage_url}
    if settings.openlineage_api_key:
        http_kwargs["auth"] = ApiKeyTokenProvider({"apiKey": settings.openlineage_api_key})
    client = OpenLineageClient(transport=HttpTransport(HttpConfig(**http_kwargs)))
    namespace = settings.openlineage_namespace or "databox"

    @dg.sensor(
        name="openlineage_sensor",
        minimum_interval_seconds=60,
        default_status=dg.DefaultSensorStatus.RUNNING,
    )
    def _openlineage_sensor(context: dg.SensorEvaluationContext) -> dg.SensorResult:
        return _openlineage_emit_tick(context, client, namespace)

    return _openlineage_sensor


def ensure_motherduck_databases() -> list[str]:
    """Create any missing MotherDuck databases this stack references.

    Called at Dagster startup. No-ops when the backend is local or when
    `MOTHERDUCK_TOKEN` is empty. Returns the list of database names that
    were ensured (for tests); the DDL itself is idempotent.
    """
    if settings.backend != "motherduck":
        return []
    if not settings.motherduck_token:
        log.warning(
            "ensure_motherduck_databases: MOTHERDUCK_TOKEN is empty, skipping CREATE DATABASE"
        )
        return []

    import duckdb

    names = settings.motherduck_database_names
    con = duckdb.connect(f"md:?motherduck_token={settings.motherduck_token}")
    try:
        for db in names:
            con.execute(f'CREATE DATABASE IF NOT EXISTS "{db}"')
    finally:
        con.close()
    return names


def dlt_destination(db_path: str) -> t.Any:
    if settings.backend == "motherduck":
        return dlt.destinations.motherduck(credentials=db_path)
    return dlt.destinations.duckdb(credentials=db_path)


def dlt_translator(raw_schema: str) -> DagsterDltTranslator:
    class _Translator(DagsterDltTranslator):
        def get_asset_spec(self, data: DltResourceTranslatorData) -> dg.AssetSpec:
            default = super().get_asset_spec(data)
            return default.replace_attributes(
                key=dg.AssetKey(["sqlmesh", raw_schema, data.resource.name])
            )

    return _Translator()


sqlmesh_config = DataboxSQLMeshContextConfig(
    path=str(MAIN_TRANSFORM_PROJECT),
    gateway=settings.gateway,
)


@sqlmesh_assets(environment="prod", config=sqlmesh_config, enabled_subsetting=True)
def sqlmesh_project(context: AssetExecutionContext, sqlmesh: SQLMeshResource):
    yield from sqlmesh.run(context=context, config=sqlmesh_config, environment="prod")


def soda_check(
    asset_key: dg.AssetKey,
    contract_path: Path,
    check_name: str = "soda_contract",
) -> dg.AssetChecksDefinition:
    @dg.asset_check(asset=asset_key, name=check_name)
    def _check() -> dg.AssetCheckResult:
        from soda_core.common.yaml import ContractYamlSource, DataSourceYamlSource
        from soda_core.contracts.contract_verification import ContractVerificationSession

        result = ContractVerificationSession.execute(
            contract_yaml_sources=[ContractYamlSource.from_str(contract_path.read_text())],
            data_source_yaml_sources=[DataSourceYamlSource.from_str(settings.soda_datasource_yaml)],
        )
        metadata: dict = {
            "checks_total": result.number_of_checks,
            "checks_passed": result.number_of_checks_passed,
            "checks_failed": result.number_of_checks_failed,
        }
        if result.is_failed:
            return dg.AssetCheckResult(
                passed=False,
                description=result.get_errors_str(),
                metadata=metadata,
            )
        return dg.AssetCheckResult(passed=True, metadata=metadata)

    return _check


# Freshness policies are per-source. Analytics marts are cross-domain and
# inherit the slowest upstream policy (NOAA GHCND, which lags several days).
FRESHNESS_BY_SOURCE: dict[str, dg.FreshnessPolicy] = {
    "ebird": dg.FreshnessPolicy.cron(
        deadline_cron="0 8 * * *", lower_bound_delta=timedelta(hours=24)
    ),
    "noaa": dg.FreshnessPolicy.cron(
        deadline_cron="0 8 * * *", lower_bound_delta=timedelta(hours=24)
    ),
    "usgs": dg.FreshnessPolicy.cron(
        deadline_cron="0 8 * * *", lower_bound_delta=timedelta(hours=24)
    ),
}


def _source_for_key(key: dg.AssetKey) -> str | None:
    path = key.path
    if len(path) < 2:
        return None
    schema = path[1]
    for src in ("ebird", "noaa", "usgs"):
        if src in schema:
            return src
    if schema == "analytics":
        return "noaa"
    return None


def apply_freshness(spec: dg.AssetSpec) -> dg.AssetSpec:
    src = _source_for_key(spec.key)
    if src is None:
        return spec
    return dg.apply_freshness_policy(spec, FRESHNESS_BY_SOURCE[src])


def freshness_checks(
    slas: dict[dg.AssetKey, timedelta],
) -> list[dg.AssetChecksDefinition]:
    """Build `last_update` freshness checks from an SLA map.

    Each entry declares the maximum tolerable staleness. A check fails when
    the asset's latest materialization timestamp is older than that window.
    One check per asset keeps the asset-check panel in Dagster readable.
    """
    checks: list[dg.AssetChecksDefinition] = []
    for key, max_lag in slas.items():
        checks.extend(
            dg.build_last_update_freshness_checks(
                assets=[key],
                lower_bound_delta=max_lag,
                severity=dg.AssetCheckSeverity.WARN,
            )
        )
    return checks


@dg.sensor(
    name="freshness_violation_sensor",
    minimum_interval_seconds=300,
    default_status=dg.DefaultSensorStatus.STOPPED,
)
def freshness_violation_sensor(context: dg.SensorEvaluationContext) -> dg.SensorResult:
    """Emit a structured log line per asset-check failure since last tick.

    Includes freshness checks (built via `freshness_checks(...)`) and any
    other asset check that failed. Transports (Slack / Email / PagerDuty)
    are the forker's choice — wire the log line into your alerting channel
    of choice. See docs/freshness.md.

    Sensor ships disabled by default (DefaultSensorStatus.STOPPED) so a
    fresh checkout does not spam a forker who has not yet picked a channel.
    """
    cursor = int(context.cursor) if context.cursor else 0
    records = context.instance.get_event_records(
        dg.EventRecordsFilter(
            event_type=dg.DagsterEventType.ASSET_CHECK_EVALUATION,
            after_cursor=cursor,
        ),
        limit=500,
        ascending=True,
    )

    latest_cursor = cursor
    for record in records:
        latest_cursor = max(latest_cursor, record.storage_id)
        event = record.event_log_entry.dagster_event
        if event is None:
            continue
        evaluation = event.event_specific_data
        if evaluation is None or evaluation.passed:  # type: ignore[union-attr]
            continue
        context.log.warning(
            "freshness_violation "
            f"asset={evaluation.asset_check_key.asset_key.to_user_string()} "  # type: ignore[union-attr]
            f"check={evaluation.asset_check_key.name} "  # type: ignore[union-attr]
            f"timestamp={record.event_log_entry.timestamp}"
        )
    return dg.SensorResult(cursor=str(latest_cursor))
