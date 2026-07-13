Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: `.10x/tickets/done/2026-07-12-repair-curated-catalog-refresh-ownership.md`, catalog-media ownership diff and focused transition tests
Verdict: pass

# Curated catalog refresh ownership self-review

## Assumptions tested

- Ordinary catalog apply/refresh cannot activate or persist a GBIF representative photo.
- Curated source exhaustion persists a typed curated placeholder rather than relabeling it as GBIF.
- A legacy GBIF photo row is not counted as valid completion and is repaired only by the explicit apply path.
- Xeno-canto call rows remain independently typed and available where eligible.
- Curated evidence is reconstructed and validated through the shared offline contract before persistence.

## Findings

No blocker or significant finding remains within this ticket.

The implementation removes `gbif_getter` from the catalog batch boundary, supplies the shared curated selector transport explicitly, builds spec-shaped typed unavailable photo evidence for hybrids/non-binomial identities, and validates curated evidence through `CuratedPhotoResult` before atomic taxon persistence. The explicit literal cast is downstream of a provider-membership guard and does not weaken runtime validation. Transition tests cover valid-curated-to-unavailable refresh and legacy-GBIF-to-curated apply repair. Xeno-canto assertions prove call ownership remains separate.

The broad pre-existing catalog tests were not used as closure evidence after orchestration narrowed this repair to the ownership-transition tests plus curated selector suite. Full aggregate gates remain required before parent closure.

## Verdict

Pass for the bounded catalog ownership repair.

## Residual risk

Full-suite and project-state verification remain deferred to the aggregate ticket. No live provider or real-data transition was performed in this repair phase.
