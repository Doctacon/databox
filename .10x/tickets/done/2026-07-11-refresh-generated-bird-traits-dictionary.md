Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: None
Depends-On: .10x/tickets/done/2026-07-09-model-avonet-traits-and-arizona-catalog.md

# Refresh generated bird-traits dictionary

## Scope

Restore the committed generated data dictionary to the current SQLMesh/Soda model metadata by regenerating `docs/dictionary/environmental_observations/dim_bird_species_traits.md` and verifying the complete dictionary/docs gate.

The aggregate Pokédex verification established that the only drift is `bird_species_traits_sk` being committed as `UNKNOWN` while current generation deterministically renders `TEXT`.

## Acceptance criteria

- `uv run --no-sync python scripts/generate_docs.py --check` passes from a clean checkout.
- `task docs:build` and MkDocs strict build pass.
- The reviewed diff contains only the expected generated dictionary correction and any mechanically required checksum artifact is not committed unless repository policy requires it.
- No implementation, model, contract, source, or live warehouse state changes.

## Explicit exclusions

No SQLMesh model/schema change, Soda contract change, AVONET reload, warehouse mutation, documentation rewrite, or adjacent cleanup.

## Evidence expectations

Record the pre-repair failing check, exact generated diff, post-repair docs checks, hooks, and clean warehouse/source state.

## Progress and notes

- 2026-07-11: Opened from aggregate verification after the canonical docs freshness command failed on one generated type: `bird_species_traits_sk` (`UNKNOWN` committed, `TEXT` generated).
- 2026-07-11: Regenerated the canonical dictionary. The reviewed implementation diff is exactly one line: `bird_species_traits_sk` changes from generated type `UNKNOWN` to `TEXT`; no other dictionary, implementation, model, contract, source, task checksum, or warehouse content changed.
- 2026-07-11: Dictionary freshness passes for all 20 generated files; `task docs:build` and MkDocs strict pass; hooks and diff checks pass. Evidence: `.10x/evidence/2026-07-11-generated-bird-traits-dictionary-refresh.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-generated-bird-traits-dictionary-refresh-review.md`.
- 2026-07-11: Retrospective found no reusable lesson beyond the existing generated-doc freshness gate; no additional record is needed.

## Blockers

None.
