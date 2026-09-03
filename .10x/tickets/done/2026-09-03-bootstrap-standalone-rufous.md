Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: .10x/tickets/done/2026-09-03-extract-rufous-repository.md
Depends-On: .10x/tickets/done/2026-09-03-export-rufous-input-artifact.md, .10x/tickets/done/2026-09-03-publish-usfws-source-interface.md

# Bootstrap standalone Rufous repository

## Scope

Create `/Users/crlough/Code/personal/rufous` as a fresh Git repository with an independently installable Python/TypeScript toolchain and a credential-free fixture-backed baseline. Copy—not yet delete from Databox—the complete Rufous product surfaces classified `move` in `.10x/research/2026-09-03-rufous-extraction-inventory.md`. Establish package identity `rufous`, separate `RUFOUS_DATABOX_PRODUCT_PATH` and `RUFOUS_DATABASE_PATH`, and pin `databox-sources` to the current immutable Databox Git revision through its public interface.

This slice establishes destination ownership and import/tooling coherence. Product SQL rewrites to `rufous_inputs_v1`, final model execution, and Databox deletion remain subsequent tickets.

## Acceptance criteria

- `/Users/crlough/Code/personal/rufous` is a new Git repository with a fresh initial extraction commit and no copied Databox Git history.
- Only source-controlled product files are copied; no `.env`, secret, DuckDB file, cache, build output, node modules, runtime state, or generated documentation is included.
- Python imports use `rufous.*`, never private `databox.*`; any temporarily unresolved cross-boundary dependency is explicitly blocked rather than copied.
- The Python manifest contains only product dependencies and pins `databox-sources` to the immutable current Databox Git revision.
- Web and worker npm manifests retain reproducible lockfiles and install independently.
- Settings distinguish a regular read-only Databox artifact path from a separate writable Rufous application database.
- A committed minimal v1 fixture artifact permits credential-free contract validation.
- Public production deployment remains disabled.
- Destination formatting, type/import checks, unit discovery, secret scan, and pre-commit pass to the extent possible before model rewrites; every deferred failing suite is enumerated with its owning follow-up ticket.
- Databox implementation is not deleted or behaviorally changed in this slice.

## Explicit exclusions

- Removing Rufous from Databox.
- Enabling public deployment.
- Rewriting product SQL models to the artifact.
- Claiming full product test parity before model/backend migration.
- Copying private Databox modules to satisfy imports.

## References

- `.10x/decisions/split-rufous-into-standalone-repository.md`
- `.10x/specs/databox-rufous-data-product-boundary.md`
- `.10x/specs/rufous-repository-extraction.md`
- `.10x/research/2026-09-03-rufous-extraction-inventory.md`

## Evidence expectations

Record the exact copied-file manifest, excluded artifacts, Git initialization/revision pin, dependency manifests, import-residue scan, settings paths, fixture validation, destination checks, intentionally deferred failures, and unchanged Databox status beyond already owned extraction records.

## Progress and notes

- 2026-09-03: Opened after the Databox artifact and public USFWS source contracts passed closure review.
- 2026-09-03: Committed Databox prerequisite boundary as `572ca6191f598e323161cdadeec3898f10913d31`, then created fresh Rufous root commit `6ba7593`. Copied 274 product-owned source files without Databox deletion; established the `rufous` package, exact Git-pinned `databox-sources`, dual database paths, read-only fixture contract, minimal tooling, and fail-closed workflow. Bootstrap Python checks passed; app typecheck/545 tests/build passed; worker 71 tests passed; secret scan passed 278 files. Full Python discovery's 18 expected migration errors and npm audit findings are explicitly owned by two follow-up tickets. Evidence: `.10x/evidence/2026-09-03-standalone-rufous-bootstrap.md`.

## Blockers

None.
