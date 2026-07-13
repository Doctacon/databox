Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-13-migrate-inaturalist-only-representative-photos.md`, exactly-once catalog and saved-plan migration
Verdict: pass

# iNaturalist-only representative-photo migration review

## Assumptions tested

- The catalog and planner apply commands each ran exactly once and never overlapped.
- Every current photo row satisfies the active iNaturalist-only contract rather than merely having an allowed provider label.
- Typed unavailable identities remain valid placeholders and cannot fail the entire catalog.
- Completion/no-op claims do not depend on a second live apply.
- Photo migration did not regenerate plans, refresh calls/sources, mutate personal or operational state, or persist binaries.
- Test and API claims remain valid against the post-migration database.

## Findings

No blocker or significant finding remains.

- **Execution boundary:** Process/lsof preflight found no competing writer. The sole catalog command completed before the sole planner command began. Logs and terminal counters show one catalog run ID and one planner apply; there was no manual deletion/reset or retry.
- **Catalog correctness:** All 706 exact current identities reconstruct as one strict result. Counts reconcile exactly: 622 available iNaturalist + 2 queried/no-eligible placeholders + 82 non-queryable identity placeholders = 706. The terminal run is complete with 624 lookups, zero remaining, bounded outcomes, and no safe failure.
- **Planner correctness:** All eight saved recommendations were replaced atomically with eight strict available iNaturalist rows. There are zero duplicates, zero invalid/missing targets, zero inserted calls, and the curated dry-run is a zero-target/zero-lookup no-op.
- **Source integrity:** Available rows use only iNaturalist; SQL finds zero Wikimedia/GBIF representative-photo rows. The live probe used only governed v2 exact identity and v1 exact-ID shortlist endpoints, selected a strict result, and performed no binary request.
- **API/browser contract:** Forbidden-discovery TestClient requests left the database hash unchanged. `/api/birds`, `/api/v1/birds`, and `/birds` returned 200; the governed JSON catalog returned 706 rows with the exact 622 available/84 placeholder split. This closes the observed `invalid unavailable photo` failure.
- **Preservation:** The 86 protected database fingerprints and 19 external hashes match before, after, and after gates. Non-photo recommendation evidence, calls, facts/timestamps, personal collection/Watches, calendar/outbox, source-refresh/credentials, warehouse/SQLMesh, and unrelated runtime state remained unchanged within those exact limits.
- **Regression evidence:** 159 focused Python tests, 145 focused frontend assertions, 776 full Python tests, 295 full frontend tests, TypeScript/build/bundle, Ruff/format/MyPy, secret/generated/docs/source-layout, SQLMesh, hooks, diff, and staging gates all pass after migration.

## Verdict

Pass. The exactly-once serialized migration satisfies the active specification and owning ticket without scope expansion. The ticket may close.

## Residual risk

Remote provider URLs and content can later change because image binaries are intentionally not stored. No physical-browser, screen-reader, responsive-device, live-image-load, or human subject-quality review was performed. `/api/v1/birds` is a successful compatibility/static route; `/api/birds` is the governed JSON catalog endpoint.
