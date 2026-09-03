Status: open
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: None

# Extract Rufous into a standalone repository

## Outcome

Create `/Users/crlough/Code/personal/rufous` as an independently testable public/private Rufous repository and reduce Databox to its platform/data-product responsibilities.

## Child sequence

1. `.10x/tickets/done/2026-09-03-inventory-rufous-extraction-boundary.md`
2. Define and implement the versioned Databox DuckDB product artifact.
3. Bootstrap the fresh Rufous repository and its independent toolchain.
4. Move product models/contracts and private backend capabilities.
5. Move web, public-release, media, and deployment capabilities.
6. Transfer governing records and documentation; add thin cross-repository indexes where needed.
7. Remove migrated Rufous surfaces from Databox and reconcile dependencies.
8. Run independent aggregate verification and adversarial review in both repositories.

Later child tickets MUST be opened from the completed inventory rather than guessing file ownership now.

## Governing records

- `.10x/decisions/split-rufous-into-standalone-repository.md`
- `.10x/specs/databox-rufous-data-product-boundary.md`
- `.10x/specs/rufous-repository-extraction.md`

## Acceptance criteria

- Every child outcome is complete and evidenced.
- Both repositories pass independently.
- Runtime coupling is limited to the versioned DuckDB artifact and pinned public `databox-sources` interface.
- Public deployment remains fail-closed.
- No secrets or local state cross the boundary.

## Progress and notes

- 2026-09-03: User selected a new sibling `rufous` repository, Databox-owned data products, Rufous-owned product schemas and USFWS orchestration, a versioned DuckDB handoff, a pinned Git dependency for `databox-sources`, and fresh destination history.
- 2026-09-03: Inventory completed at `.10x/research/2026-09-03-rufous-extraction-inventory.md`; it proposes the exact artifact, package boundary, ownership manifest, and bounded sequence.

## Blockers

Ratify the inventory's six decisions: iNaturalist ownership, source-refresh UI, artifact distribution, artifact namespaces, private-location posture, and post-split Databox USFWS orchestration.
