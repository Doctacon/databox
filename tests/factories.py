"""Schema-driven fake data generation for any dlt resource."""

from __future__ import annotations

from typing import Any

from faker import Faker

fake = Faker()
Faker.seed(42)

TYPE_GENERATORS: dict[str, Any] = {
    "bigint": lambda: fake.random_int(min=0, max=10000),
    "biguint": lambda: fake.random_int(min=0, max=10000),
    "int": lambda: fake.random_int(min=0, max=1000),
    "integer": lambda: fake.random_int(min=0, max=1000),
    "double": lambda: float(round(fake.pyfloat(min_value=-180, max_value=180), 6)),
    "float": lambda: float(round(fake.pyfloat(min_value=-180, max_value=180), 6)),
    "float8": lambda: float(round(fake.pyfloat(min_value=-180, max_value=180), 6)),
    "text": lambda: fake.word(),
    "varchar": lambda: fake.word(),
    "string": lambda: fake.word(),
    "bool": lambda: fake.boolean(),
    "boolean": lambda: fake.boolean(),
    "timestamp": lambda: fake.date_time().isoformat(),
    "timestamptz": lambda: fake.date_time().isoformat(),
    "date": lambda: fake.date().isoformat(),
    "time": lambda: fake.time(),
    "decimal": lambda: round(fake.pyfloat(min_value=0, max_value=1000), 2),
    "json": lambda: {},
    "binary": lambda: b"data",
    "blob": lambda: b"data",
    "bytes": lambda: b"data",
}

NAME_HINTS: dict[str, Any] = {
    "lat": lambda: float(round(fake.latitude(), 6)),
    "latitude": lambda: float(round(fake.latitude(), 6)),
    "lng": lambda: float(round(fake.longitude(), 6)),
    "longitude": lambda: float(round(fake.longitude(), 6)),
    "lon": lambda: float(round(fake.longitude(), 6)),
    "email": lambda: fake.email(),
    "phone": lambda: fake.phone_number(),
    "url": lambda: fake.url(),
    "name": lambda: fake.name(),
    "first_name": lambda: fake.first_name(),
    "last_name": lambda: fake.last_name(),
    "city": lambda: fake.city(),
    "country": lambda: fake.country_code(),
    "state": lambda: fake.state_abbr(),
    "zip": lambda: fake.zipcode(),
    "address": lambda: fake.address(),
    "description": lambda: fake.sentence(),
    "title": lambda: fake.sentence(),
    "code": lambda: fake.bothify("??####").lower(),
    "id": lambda: fake.uuid4(),
    "date": lambda: fake.date().isoformat(),
    "datetime": lambda: fake.date_time().isoformat(),
    "timestamp": lambda: fake.date_time().isoformat(),
    "count": lambda: fake.random_int(min=0, max=1000),
    "total": lambda: fake.random_int(min=0, max=10000),
    "amount": lambda: round(fake.pyfloat(min_value=0, max_value=1000), 2),
    "price": lambda: round(fake.pyfloat(min_value=0, max_value=500), 2),
    "percent": lambda: round(fake.pyfloat(min_value=0, max_value=100), 1),
    "score": lambda: fake.random_int(min=0, max=100),
    "order": lambda: fake.random_int(min=0, max=1000),
    "region": lambda: fake.bothify("??-??").upper(),
}


def _generate_value(col_name: str, col_spec: dict | None = None) -> Any:
    """Generate a single fake value based on column name and type spec."""
    name_lower = col_name.lower()

    for key, gen in NAME_HINTS.items():
        if key in name_lower:
            return gen()

    if col_spec and "data_type" in col_spec:
        dtype = col_spec["data_type"].lower()
        if dtype in TYPE_GENERATORS:
            return TYPE_GENERATORS[dtype]()

    return fake.word()


def generate_row(
    columns: dict[str, dict] | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a single row of fake data.

    Args:
        columns: dlt column hints like {"howMany": {"data_type": "bigint"}, ...}
        extra_fields: additional fields to include or override
    """
    row: dict[str, Any] = {}

    if columns:
        for col_name, col_spec in columns.items():
            row[col_name] = _generate_value(col_name, col_spec)

    if extra_fields:
        row.update(extra_fields)

    return row


def generate_rows(
    n: int = 10,
    columns: dict[str, dict] | None = None,
    extra_fields: dict[str, Any] | None = None,
    unique_key: str | None = None,
) -> list[dict[str, Any]]:
    """Generate N rows of fake data.

    Args:
        n: number of rows
        columns: dlt column hints
        extra_fields: additional fields per row
        unique_key: if set, ensures this field is unique across all rows
    """
    rows: list[dict[str, Any]] = []
    seen: set = set()

    for _i in range(n):
        row = generate_row(columns=columns, extra_fields=extra_fields)

        if unique_key and unique_key in row:
            base = row[unique_key]
            counter = 0
            while row[unique_key] in seen:
                row[unique_key] = f"{base}_{counter}"
                counter += 1
            seen.add(row[unique_key])

        rows.append(row)

    return rows


def generate_resource_data(resource, n: int = 10) -> list[dict[str, Any]]:
    """Generate fake data matching a dlt resource's column spec.

    Args:
        resource: a dlt DltResource object
        n: number of rows to generate
    """
    columns = resource.columns if hasattr(resource, "columns") else {}
    extra: dict[str, Any] = {"_loaded_at": fake.date_time().isoformat()}
    return generate_rows(n=n, columns=columns, extra_fields=extra)
