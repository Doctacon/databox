Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: .10x/tickets/2026-09-03-extract-rufous-repository.md
Depends-On: .10x/tickets/done/2026-09-03-inventory-rufous-extraction-boundary.md

# Export the versioned Rufous input artifact

## Scope

Implement the local, atomic, versioned DuckDB data-product artifact specified by `.10x/specs/databox-rufous-data-product-boundary.md` and the exact twelve-relation inventory in `.10x/research/2026-09-03-rufous-extraction-inventory.md`.

Freeze each projection's ordered columns and types from current authoritative models/source tables before coding. Export `databox_product_meta.contract`, `databox_product_meta.relations`, and the twelve `rufous_inputs_v1` relations. Add a contract validator and fixture-backed operator command.

## Acceptance criteria

- Export is deterministic, bounded, atomic, and produces a regular DuckDB file.
- Contract metadata contains one `rufous-inputs` schema-version-1 row, producer Git revision/version, generation time, canonical contract SHA-256, and one relation record per output with ordered-schema hash and row count.
- Consumer validation fails on missing/duplicate metadata, unsupported version, missing relation, schema mismatch, non-regular path, or writable attachment.
- `public_bird_observation` includes only valid, reviewed, non-private rows and no other observation-location interface is exported.
- No secret, application state, unrelated schema, raw private eBird relation, or product-owned iNaturalist state is present.
- A credential-free deterministic fixture proves export and read-only consumption.
- Databox CI, SQLMesh tests, docs, pre-commit, and secret scan pass.

## Explicit exclusions

- Remote artifact publication.
- Destination repository creation.
- Product model movement.
- Private-location export.

## References

- `.10x/decisions/split-rufous-into-standalone-repository.md`
- `.10x/specs/databox-rufous-data-product-boundary.md`
- `.10x/research/2026-09-03-rufous-extraction-inventory.md`

## Evidence expectations

Record frozen schemas, privacy queries, deterministic hashes, atomic failure behavior, artifact inventory, test output, and residual compatibility limits.

## Progress and notes

- 2026-09-03: User ratified the proposed schema names, local-only distribution, and public-safe observation boundary.
- 2026-09-03: Implemented and live-verified an initial twelve-relation artifact with static v1 schema hashes, public-safe filtering, read-only attachment, row bounds, CLI, and credential-free frozen-schema fixtures. Focused verification passed (52 tests), Ruff, format, targeted MyPy, and diff checks passed.
- 2026-09-03: Independent review rejected closure. Review: `.10x/reviews/2026-09-03-rufous-input-boundary-review.md`.
- 2026-09-03: Repaired every review finding: all source schema validation/count/transfer reads now share one DuckDB transaction; resolved equal source/output paths fail before opening; source schemas are checked before row transfer; deterministic provenance snapshot IDs are required for nonempty raw snapshots with explicit null-only policy for empty or modeled relations; exact validation rejects views/unexpected schemas and incomplete contract/relation metadata. Added adversarial tests. Full CI passed (1,514 tests), SQLMesh 18/18, strict docs, pre-commit, secret scan, diff and unstaged checks passed.
- 2026-09-03: Final review found two residual integrity gaps; provenance is now recomputed and both metadata table schemas are validated exactly. Six artifact tests, Ruff, formatting, MyPy, and diff checks passed. Closure review passed.

## Blockers

None.
