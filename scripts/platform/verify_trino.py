"""Exercise Trino's Iceberg table and REST view lifecycle in an isolated namespace.

Uses existing warehouse credentials through the Trino service. Never touches raw
or production model tables. Drops only the uniquely named objects it creates.
"""

from __future__ import annotations

import uuid

from databox.config.settings import settings
from trino.dbapi import connect


def main() -> None:
    schema = f"trino_probe_{uuid.uuid4().hex[:12]}"
    connection = connect(
        host=settings.trino_host,
        port=settings.trino_port,
        user="databox",
        catalog="databox",
        http_scheme="http",
    )
    cursor = connection.cursor()
    created = False
    try:
        cursor.execute(f"CREATE SCHEMA databox.{schema}").fetchall()
        created = True
        cursor.execute(f"CREATE TABLE databox.{schema}.probe (id BIGINT, value VARCHAR)").fetchall()
        cursor.execute(f"INSERT INTO databox.{schema}.probe VALUES (1, 'first')").fetchall()
        cursor.execute(
            f"UPDATE databox.{schema}.probe SET value = 'updated' WHERE id = 1"
        ).fetchall()
        cursor.execute(
            f"CREATE VIEW databox.{schema}.probe_view AS SELECT * FROM databox.{schema}.probe"
        ).fetchall()
        assert cursor.execute(f"SELECT * FROM databox.{schema}.probe_view").fetchall() == [
            [1, "updated"]
        ]
        cursor.execute(f"DELETE FROM databox.{schema}.probe WHERE id = 1").fetchall()
        assert cursor.execute(f"SELECT count(*) FROM databox.{schema}.probe").fetchall() == [[0]]
        print("TRINO_OK create/insert/update/view/select/delete")
    finally:
        try:
            if created:
                cursor.execute(f"DROP VIEW IF EXISTS databox.{schema}.probe_view").fetchall()
                cursor.execute(f"DROP TABLE IF EXISTS databox.{schema}.probe").fetchall()
                cursor.execute(f"DROP SCHEMA databox.{schema}").fetchall()
                print("TRINO_OK cleanup")
        finally:
            connection.close()


if __name__ == "__main__":
    main()
