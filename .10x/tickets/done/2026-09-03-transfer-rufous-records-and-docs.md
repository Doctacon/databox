Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: .10x/tickets/done/2026-09-03-extract-rufous-repository.md
Depends-On: .10x/tickets/done/2026-09-03-migrate-rufous-models-and-backend.md, .10x/tickets/done/2026-09-03-migrate-rufous-web-public-deployment.md

# Transfer Rufous records and reconcile documentation

## Scope

Apply the semantic `.10x` ownership rules in `.10x/research/2026-09-03-rufous-extraction-inventory.md`. Transfer Rufous product authority and relevant history into the standalone repository, add its own concise repository instructions/index, and replace Databox active product authority with thin cross-repository pointers where Databox still needs provenance. Reconcile READMEs, commands, docs navigation, generated-dictionary ownership, and cross-references in both repositories.

## Acceptance criteria

- An explicit reviewed path manifest classifies every transferred active decision/spec/knowledge record and every imported historical research/evidence/review/ticket record.
- Rufous has one canonical active copy of every product behavioral contract needed for cold-start maintenance.
- Databox has no duplicate active Rufous product authority; retained historical records are clearly historical or superseded, while thin pointers name the canonical Rufous repository and source Databox revision.
- Extraction/platform boundary records remain canonical in Databox until aggregate closure; Rufous receives a thin boundary index rather than divergent active copies.
- Rufous documentation contains no Databox-local links, nonexistent commands, stale Quack paths, or generated pages copied as authority.
- Databox documentation no longer presents itself as the Rufous application owner.
- Dictionary/index/lineage pages are regenerated independently from each repository's owned models.
- Record headers, references, statuses, and terminal paths are coherent; no secret or unnecessary sensitive history is copied.
- Both repositories' record/reference, docs, pre-commit, and secret checks pass.

## Explicit exclusions

- Deleting Databox implementation; owned by the subsequent prune ticket.
- Enabling production.
- Rewriting Git history.
- Copying all keyword-matching records without semantic inspection.

## References

- `.10x/specs/rufous-repository-extraction.md`
- `.10x/research/2026-09-03-rufous-extraction-inventory.md`
- `.10x/evidence/2026-09-03-standalone-rufous-bootstrap.md`
- `.10x/evidence/2026-09-03-rufous-models-and-backend-migration.md`
- `.10x/evidence/2026-09-03-rufous-web-public-deployment-migration.md`

## Evidence expectations

Record exact copy/move/pointer manifest, canonical-authority checks, repaired references, generated-doc diffs, residue scans, commands, and residual historical limitations.

## Progress and notes

- 2026-09-03: Opened after standalone product code, models, web, and deployment migrations passed bounded reviews.
- 2026-09-03: Moved 49 active product records, imported 283 explicitly listed historical records into the non-authoritative destination history tree, added split/boundary indexes, and reconciled Databox README/MkDocs ownership. Bounded diff, secret, pre-commit, and residue checks passed. Evidence: `.10x/evidence/2026-09-03-rufous-record-transfer.md`; destination manifest: `https://github.com/Doctacon/rufous/blob/main/.10x/research/2026-09-03-databox-record-transfer-manifest.md`.

- 2026-09-03: Post-transfer review found stale shared-database/Quack ownership in six canonical Rufous records. Added the standalone data-product boundary decision, moved two immutable obsolete decisions to `decisions/superseded/`, rewrote four active specs around read-only artifact input and separate writable Rufous state, repaired references, and corrected the residual Databox README sentence.

## Blockers

None.
