# ADR-0006: MotherDuck as the cloud path

**Status:** Superseded · 2026-07 by the local-only platform decision in
[ADR-0007](0007-quack-single-file-local-ingest.md) and
[`.10x/decisions/local-only-birding-product-architecture.md`](https://github.com/Doctacon/databox/blob/main/.10x/decisions/local-only-birding-product-architecture.md)

> Historical record only. MotherDuck is no longer a supported backend. The
> configuration and commands below describe the former implementation and MUST
> NOT be used as current setup instructions.

## Context

The local stack was considered insufficient for sharing data across laptops or
publishing a live portfolio dashboard. Managed warehouses, object storage plus
a query service, MotherDuck, and self-hosted DuckDB were evaluated as possible
cloud paths.

## Historical decision

MotherDuck was selected as a cloud DuckDB path while local DuckDB remained the
default. The former implementation selected local or cloud database URIs,
dlt destinations, and SQLMesh gateways with an environment variable.

## Supersession rationale

The product is now explicitly local-only. A cloud warehouse and Dive
publication path add deployment, authentication, synchronization, proprietary
service, and application-state complexity without serving the personal local
product. Databox now has one supported warehouse path:
`data/databox.duckdb`, written through Quack and transformed through the local
SQLMesh gateway.

Historical changelog and terminal project records retain the old decision as
factual history. Active configuration, runtime code, tests, task commands, and
setup documentation do not expose the former cloud path.
