"""Shared Dagster wiring primitives — used by every domain module.

Anything that is cross-domain (the single SQLMesh multi-asset, dlt and
Soda factory helpers, the SQLMesh translator, the freshness policy
applier) lives here. Domain modules compose these primitives without
knowing about each other.
"""

import typing as t
from datetime import timedelta
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
