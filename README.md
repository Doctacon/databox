# Databox

[![CI](https://github.com/Doctacon/databox/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/Doctacon/databox/actions/workflows/ci.yaml)
[![Docs](https://github.com/Doctacon/databox/actions/workflows/docs.yaml/badge.svg?branch=main)](https://doctacon.github.io/databox/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A local-first data warehouse built around DuckDB. Databox ingests public data
with dlt, transforms it with SQLMesh, validates it with Soda, and orchestrates
everything in Dagster—without always-on infrastructure.

```text
public sources → dlt → DuckDB → SQLMesh → Soda
                         ↑
                      Dagster
```

The included Rufous bird app is a reference consumer of the warehouse, not the
core of the project.

## Quickstart

```bash
task install
cp .env.example .env
$EDITOR .env
task full-refresh      # build data/databox.duckdb
task dagster:dev       # open Dagster at localhost:3000
```

## Details

- [Documentation and data dictionary](https://doctacon.github.io/databox/)
- [Architecture decisions](docs/adr/)
- [Configuration](docs/configuration.md)
- [Commands](docs/commands.md)
- [Adding a source](docs/new-source.md)

## License

[MIT](LICENSE)
