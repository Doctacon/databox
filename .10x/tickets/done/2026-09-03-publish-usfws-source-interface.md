Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: .10x/tickets/done/2026-09-03-extract-rufous-repository.md
Depends-On: .10x/tickets/done/2026-09-03-inventory-rufous-extraction-boundary.md

# Publish the reusable USFWS source interface

## Scope

Expose the existing provider-level USFWS implementation through a stable public `databox_sources.usfws` import for a Rufous Git-pinned dependency. Move no Rufous targeting or publication semantics into that interface.

## Acceptance criteria

- `databox_sources.usfws` publicly exports `usfws_source`, `USFWS_MAX_TARGET_SPECIES`, and the minimal typed target mapping contract.
- The public interface exposes no Databox settings, credentials, Dagster assets, DuckDB paths, Polaris client, Rufous target derivation, approval, or publication helper.
- An isolated package test imports only the public interface and runs cassette-backed explicit-target extraction.
- Existing bounded requests, facet validation, licensing metadata capture, current-run support, and provider safety tests remain unchanged.
- Documentation states that Rufous pins an immutable Databox Git tag or commit.
- Databox CI and package tests pass.

## Explicit exclusions

- Removing the current Databox USFWS Dagster job before Rufous replacement verification.
- Rufous repository creation.
- iNaturalist public API expansion; its product-specific source moves to Rufous.
- Package registry publication.

## References

- `.10x/decisions/split-rufous-into-standalone-repository.md`
- `.10x/specs/databox-rufous-data-product-boundary.md`
- `.10x/research/2026-09-03-rufous-extraction-inventory.md`

## Evidence expectations

Record exported symbols, isolated import surface, cassette-backed results, dependency inspection, and test output.

## Progress and notes

- 2026-09-03: User ratified a Git-pinned public package interface, Rufous-owned target-bearing orchestration, and Databox retention of source primitives only after destination verification.
- 2026-09-03: Exported exactly `usfws_source`, `USFWS_MAX_TARGET_SPECIES`, and `UsfwsTarget`; added an explicit-target public-interface pipeline test and immutable Git pin documentation. All USFWS and focused tests passed.
- 2026-09-03: Independent review rejected closure. Review: `.10x/reviews/2026-09-03-rufous-input-boundary-review.md`.
- 2026-09-03: Replaced the generated transport in the public-interface proof with a genuinely recorded, sanitized, bounded Berylline Hummingbird USFWS cassette and verified offline playback with network blocking. Updated the protected fixture manifest. Full CI passed (1,514 tests), SQLMesh 18/18, strict docs, pre-commit, secret scan, diff and unstaged checks passed.
- 2026-09-03: Final closure review confirmed the exact three-symbol public interface and genuine offline recorded cassette. Review passed.

## Blockers

None.
