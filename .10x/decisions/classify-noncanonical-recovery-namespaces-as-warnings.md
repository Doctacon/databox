Status: active
Created: 2026-09-09
Updated: 2026-09-09

# Classify noncanonical recovery namespaces as warnings

## Context

Restored Polaris validation proved all 25 registry-owned tables readable but also found historical `raw_usfws` and test `dlt_polaris_probe` namespaces. These namespaces are outside the canonical seven-source registry. Treating their mere presence as corruption blocks otherwise valid recovery; silently ignoring or deleting them would hide catalog state and exceed recovery authority.

## Decision

Recovery validation MUST derive canonical namespaces from the source registry. Every namespace and table outside that set MUST remain explicitly enumerated as noncanonical warning state and MUST NOT by itself cause a nonzero result. An undeclared table inside a canonical namespace remains unexpected failure state. Missing, malformed, or unreadable canonical state remains failure state.

Validation MUST NOT silently allowlist identifiers, delete noncanonical state, or imply that warning state is canonical or supported. Catalog cleanup remains separately authorized.

## Alternatives considered

- Fail on every noncanonical namespace: rejected because historical/test namespaces do not invalidate recovery of the governed catalog surface.
- Ignore or automatically delete extras: rejected because it hides evidence and introduces destructive behavior.

## Consequences

A restore can pass with prominent noncanonical warnings when every canonical table validates. Operators retain visibility and can pursue cleanup separately. Drift inside governed namespaces continues to fail closed.
