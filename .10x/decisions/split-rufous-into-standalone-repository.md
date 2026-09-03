Status: active
Created: 2026-09-03
Updated: 2026-09-03

# Split Rufous into a standalone repository

## Context

Databox currently combines a reusable ingestion/analytics platform with the private and public Rufous birding product. This obscures repository identity, expands onboarding and dependency scope, and couples product deployment to platform internals.

## Decision

Create a fresh sibling Git repository at `/Users/crlough/Code/personal/rufous` for all public and private Rufous product behavior. Databox remains the owner of source ingestion and reusable modeled data products.

Databox will export a bounded, versioned DuckDB data-product artifact. Rufous will attach that artifact read-only and maintain its own application database. Product schemas `birding_agent` and `rufous_public` move to Rufous; generic `environmental_observations` and `analytics.platform_health` remain in Databox.

USFWS source implementation remains a documented public interface of `databox-sources`. Rufous owns target derivation and its manual unscheduled workflow through a Databox Git tag/commit dependency.

The Rufous repository begins with a fresh extraction commit rather than rewritten or cloned Databox history.

## Alternatives considered

- Keep Rufous in Databox: rejected because the combined repository has an unclear product/platform identity.
- Move all bird ingestion to Rufous: rejected because Databox owns reusable source ingestion and governed data products.
- Directly attach Databox's working database: rejected because it couples Rufous to repository path and mutable runtime state.
- Let Rufous read raw Polaris tables: rejected because it duplicates transformation infrastructure and expands credentials.
- Copy the USFWS implementation: rejected because two source implementations would drift.

## Consequences

Both repositories gain narrower ownership and independent release surfaces. A versioned artifact contract and a stable public `databox-sources` interface become compatibility obligations. Cross-repository changes require explicit contract versioning. Rufous cannot depend on private Databox Python modules, working database paths, or deployment workflows.
