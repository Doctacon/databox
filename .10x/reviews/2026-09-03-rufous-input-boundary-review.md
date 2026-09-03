Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Target: .10x/tickets/done/2026-09-03-export-rufous-input-artifact.md, .10x/tickets/done/2026-09-03-publish-usfws-source-interface.md
Verdict: pass

# Rufous input boundary review

## Findings and resolution

The first independent review rejected closure because export reads were not one coherent snapshot, source/output equality was unsafe, snapshot identifiers were absent, exact catalog/metadata validation was incomplete, the USFWS proof was not cassette-backed, and aggregate gates were absent. Remediation established one source transaction around schema/count/transfer reads, rejects resolved path equality before opening the source, emits deterministic provenance hashes for nonempty raw relations, rejects unexpected tables/views/schemas, and added a real offline recorded USFWS cassette. Aggregate CI, SQLMesh, strict docs, pre-commit, secret, diff, and no-staged-files gates passed.

A second review found two remaining significant gaps: provenance identifiers were shape-checked but not recomputed, and metadata table schemas allowed extra columns. Final repair requires exactly 64 lowercase hexadecimal provenance characters, compares every required identifier with recomputed relation content, and validates ordered names/types/nullability for both metadata tables. Adversarial tests reject tampered provenance and extra metadata columns.

No unresolved critical or significant finding remains. Public observations remain valid/reviewed/non-private only; the consumer attachment is read-only; the public USFWS package exposes exactly the three ratified provider symbols.

## Residual risk

The transaction protects Databox-managed source reads; external storage mutation bypassing Databox orchestration is outside this local export contract. Remote artifact distribution remains excluded.

## Verdict

Pass.
