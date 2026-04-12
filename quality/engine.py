"""Data quality engine — pure functions for checking and reporting on loaded data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from config.pipeline_config import PipelineConfig


def check_table(table: str, db_path: Path) -> dict:
    """Run basic quality checks on a table.

    Returns a dict with row_count, null_counts, and latest_load.
    Raises on connection or query failure.
    """
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        row_count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        cols = con.execute(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = '{table.split('.')[-1]}'"
        ).fetchall()

        null_counts = []
        for (col,) in cols:
            n = con.execute(f'SELECT COUNT(*) FROM {table} WHERE "{col}" IS NULL').fetchone()[0]
            null_counts.append((col, n))

        try:
            latest_load = con.execute(f"SELECT MAX(_loaded_at) FROM {table}").fetchone()[0]
        except Exception:
            latest_load = None

        return {
            "table": table,
            "row_count": row_count,
            "null_counts": null_counts,
            "latest_load": str(latest_load) if latest_load else None,
        }
    finally:
        con.close()


def run_report(db_path: Path, configs: dict[str, PipelineConfig]) -> list[dict]:
    """Run all configured quality rules against loaded data.

    Returns a list of result dicts, each with keys:
      pipeline, table, rows, freshness, rule, status
    """
    con = duckdb.connect(str(db_path), read_only=True)
    results: list[dict] = []

    try:
        for name, cfg in configs.items():
            schema = cfg.resolve_schema_name()

            tables = con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
                [schema],
            ).fetchall()
            table_names = [t[0] for t in tables]

            for tbl in table_names:
                fqn = f'"{schema}"."{tbl}"'
                count = con.execute(f"SELECT COUNT(*) FROM {fqn}").fetchone()[0]

                try:
                    latest = con.execute(f"SELECT MAX(_loaded_at) FROM {fqn}").fetchone()[0]
                except Exception:
                    latest = None

                results.append(
                    {
                        "pipeline": name,
                        "table": f"{schema}.{tbl}",
                        "rows": count,
                        "freshness": str(latest) if latest else "N/A",
                        "rule": "(row count)",
                        "status": "OK" if count > 0 else "FAIL",
                    }
                )

            for rule in cfg.quality_rules:
                target_table = table_names[0] if table_names else None
                if not target_table:
                    results.append(
                        {
                            "pipeline": name,
                            "table": f"{schema}.?",
                            "rows": 0,
                            "freshness": "N/A",
                            "rule": f"{rule.check}({rule.column})",
                            "status": "SKIP",
                        }
                    )
                    continue

                fqn = f'"{schema}"."{target_table}"'
                rule_desc = f"{rule.check}({rule.column})"

                try:
                    if rule.check == "not_null":
                        violations = con.execute(
                            f'SELECT COUNT(*) FROM {fqn} WHERE "{rule.column}" IS NULL'
                        ).fetchone()[0]
                        status = "OK" if violations == 0 else f"FAIL ({violations} nulls)"

                    elif rule.check == "unique":
                        dupes = con.execute(
                            f'SELECT COUNT(*) - COUNT(DISTINCT "{rule.column}") FROM {fqn}'
                        ).fetchone()[0]
                        status = "OK" if dupes == 0 else f"FAIL ({dupes} duplicates)"

                    elif rule.check == "range" and rule.threshold is not None:
                        col_type = con.execute(
                            "SELECT data_type FROM information_schema.columns "
                            f"WHERE table_schema = '{schema}' AND table_name = '{target_table}' "
                            f"AND column_name = '{rule.column}'"
                        ).fetchone()
                        if col_type:
                            query = f'SELECT COUNT(*) FROM {fqn} WHERE "{rule.column}" > {rule.threshold}'
                            out_of_range = con.execute(query).fetchone()[0]
                            status = (
                                "OK"
                                if out_of_range == 0
                                else f"FAIL ({out_of_range} over {rule.threshold})"
                            )
                        else:
                            status = "SKIP (column not found)"

                    elif rule.check == "accepted_values" and rule.values:
                        val_list = ", ".join(f"'{v}'" for v in rule.values)
                        invalid = con.execute(
                            f'SELECT COUNT(*) FROM {fqn} WHERE "{rule.column}" NOT IN ({val_list})'
                        ).fetchone()[0]
                        status = "OK" if invalid == 0 else f"FAIL ({invalid} invalid)"

                    else:
                        status = "SKIP (unknown check)"

                except Exception as e:
                    status = f"ERROR ({e})"

                results.append(
                    {
                        "pipeline": name,
                        "table": f"{schema}.{target_table}",
                        "rows": 0,
                        "freshness": "",
                        "rule": rule_desc,
                        "status": status,
                    }
                )
    finally:
        con.close()

    return results
