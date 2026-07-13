Status: active
Created: 2026-07-13
Updated: 2026-07-13

# Curated-photo operation invariants

## Purpose

Reusable rules for explicit metadata-only media campaigns whose selector can make multiple provider requests per identity and whose results must remain resumable across interruption, process restart, and prior campaign state.

## Campaign ownership

A campaign is complete only when every current identity has one strict terminal result owned by the authoritative campaign. Global valid-row cardinality is not campaign completion: valid rows from an earlier campaign may satisfy presentation while lacking the current campaign checkpoint and outcome accounting.

When an earlier terminal result can be adopted deterministically without provider access—such as a non-queryable hybrid placeholder—the supported resume path may atomically re-own it. The run must record that terminal outcome while preserving already owned current-campaign rows. Never repair campaign ownership through manual SQL deletion or counter edits.

## Lookup and request accounting

Count logical identity lookups separately from actual provider request attempts. Persist request attempts as soon as transport returns, before coupling them to result persistence, because interruption after transport is still operational truth. A two-stage identity/metadata selector may produce zero, one, or two attempts per lookup.

Run records should contain bounded status, target/checkpoint/processed counts, logical lookups, actual requests, provider/outcome/failure totals, start/completion/duration, and sanitized failure text.

## Retryable versus terminal unavailable

Unavailable is valid presentation data, but it is not always a terminal checkpoint.

- Terminal: non-queryable identity, exact identity rejection, or successfully exhausted curated shortlist.
- Retryable: transport, throttle, budget, or provider-schema failure.

Persist both safely for placeholder presentation, but exclude retryable results from completion. Explicit photo-only reruns should target only retryable/missing/invalid results and become network/write no-ops after terminal success.

## Shared rate state and deterministic tests

Local processes must coordinate provider minute/day budgets through atomically locked durable state. Tests with fake transports must always receive isolated temporary state or an explicit no-op limiter. Otherwise deterministic tests can silently mutate production rate state even when no real provider call occurs.

External fingerprints should include owned operational sidecars. If a sidecar is expected to change, classify it explicitly rather than weakening all external-state comparisons.

## Evidence durability

Store sanitized fingerprint procedures, raw digest/count artifacts, exact commands or bounded logs, and a checksum manifest under `.10x/evidence/.storage/`. Use repository-visible extensions such as `.json`, `.py`, and `.txt`; avoid ignored extensions such as `.log`. Fingerprint artifacts may contain schema and column names, counts, and hashes, but must not contain personal row values, credentials, raw provider payloads, coordinates, or arbitrary URLs.
