"""Data quality engine — pure functions for checking and reporting on loaded data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import psycopg2

if TYPE_CHECKING:
    from databox.config.pipeline_config import PipelineConfig


def _fetchone_value(cur: psycopg2.extensions.cursor) -> Any:
    row = cur.fetchone()
    assert row is not None
    return row[0]


def check_table(table: str, database_url: str) -> dict:
    """Run basic quality checks on a table.

    Returns a dict with row_count, null_counts, and latest_load.
    Raises on connection or query failure.
    """
    con = psycopg2.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = _fetchone_value(cur)

        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table.split(".")[-1],),
        )
        cols = cur.fetchall()

        null_counts = []
        for (col,) in cols:
            cur.execute(f'SELECT COUNT(*) FROM {table} WHERE "{col}" IS NULL')
            n = _fetchone_value(cur)
            null_counts.append((col, n))

        try:
            cur.execute(f"SELECT MAX(_loaded_at) FROM {table}")
            latest_load = _fetchone_value(cur)
        except Exception:
            con.rollback()
            latest_load = None

        return {
            "table": table,
            "row_count": row_count,
            "null_counts": null_counts,
            "latest_load": str(latest_load) if latest_load else None,
        }
    finally:
        con.close()


def run_report(database_url: str, configs: dict[str, PipelineConfig]) -> list[dict]:
    """Run all configured quality rules against loaded data.

    Returns a list of result dicts, each with keys:
      pipeline, table, rows, freshness, rule, status
    """
    con = psycopg2.connect(database_url)
    results: list[dict] = []

    try:
        cur = con.cursor()

        for name, cfg in configs.items():
            schema = cfg.resolve_schema_name()

            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                (schema,),
            )
            table_names = [t[0] for t in cur.fetchall()]

            for tbl in table_names:
                fqn = f'"{schema}"."{tbl}"'
                cur.execute(f"SELECT COUNT(*) FROM {fqn}")
                count = _fetchone_value(cur)

                try:
                    cur.execute(f"SELECT MAX(_loaded_at) FROM {fqn}")
                    latest = _fetchone_value(cur)
                except Exception:
                    con.rollback()
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
                        cur.execute(f'SELECT COUNT(*) FROM {fqn} WHERE "{rule.column}" IS NULL')
                        violations = _fetchone_value(cur)
                        status = "OK" if violations == 0 else f"FAIL ({violations} nulls)"

                    elif rule.check == "unique":
                        cur.execute(f'SELECT COUNT(*) - COUNT(DISTINCT "{rule.column}") FROM {fqn}')
                        dupes = _fetchone_value(cur)
                        status = "OK" if dupes == 0 else f"FAIL ({dupes} duplicates)"

                    elif rule.check == "range" and rule.threshold is not None:
                        cur.execute(
                            "SELECT data_type FROM information_schema.columns "
                            "WHERE table_schema = %s AND table_name = %s "
                            "AND column_name = %s",
                            (schema, target_table, rule.column),
                        )
                        col_type = cur.fetchone()
                        if col_type:
                            cur.execute(
                                f'SELECT COUNT(*) FROM {fqn} WHERE "{rule.column}" > %s',
                                (rule.threshold,),
                            )
                            out_of_range = _fetchone_value(cur)
                            status = (
                                "OK"
                                if out_of_range == 0
                                else f"FAIL ({out_of_range} over {rule.threshold})"
                            )
                        else:
                            status = "SKIP (column not found)"

                    elif rule.check == "accepted_values" and rule.values:
                        val_list = ", ".join(f"'{v}'" for v in rule.values)
                        cur.execute(
                            f'SELECT COUNT(*) FROM {fqn} WHERE "{rule.column}" NOT IN ({val_list})'
                        )
                        invalid = _fetchone_value(cur)
                        status = "OK" if invalid == 0 else f"FAIL ({invalid} invalid)"

                    else:
                        status = "SKIP (unknown check)"

                except Exception as e:
                    con.rollback()
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
