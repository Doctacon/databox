Status: done
Created: 2026-07-11
Updated: 2026-07-12
Parent: `.10x/tickets/done/2026-07-11-upgrade-representative-bird-photos.md`
Depends-On: `.10x/tickets/done/2026-07-11-implement-curated-photo-selector.md`

# Migrate catalog and Field Map to curated photos

## Scope

Integrate the curated selector into runtime catalog media, catalog/profile APIs, Field Map's species-keyed catalog-photo reuse, strict TypeScript validators, attribution labels, and tests. Extend the explicit catalog-media command with inspect/dry-run and resumable photo-only full refresh semantics.

After code and non-live gates pass, run the explicitly authorized live migration over all 706 catalog rows while Quack/SQLMesh and other writers are inactive. Reevaluate all 624 species; persist hybrids/unresolved identities unavailable without lookup. Publish atomically per species and resume safely after interruption.

## Acceptance criteria

- Catalog/profile/map APIs accept only valid `wikimedia_commons` or `inaturalist` representative-photo objects and reject source/URL/license/dimension/identity mismatches.
- Browser labels and links identify the actual provider rather than hard-coded GBIF; loading remains lazy and failures preserve attribution/placeholders.
- Field Map reuses exactly the catalog photo object and performs no discovery or separate map-media persistence.
- Dry-run performs zero provider calls and zero writes.
- Full explicit refresh replaces every current catalog GBIF/unavailable photo row with one current curated available/unavailable result; no legacy GBIF representative result is retained as fallback.
- Interrupted/rerun behavior is covered and idempotent for completed current identities.
- Call rows, catalog facts, observations, Watches, calendar/outbox, refresh state, and all unrelated runtime/warehouse tables remain unchanged, with pre/post safe checksums or bounded row/value comparisons.
- No model, email, routine source refresh, AVONET refresh, or media binary request occurs.
- Focused backend/frontend tests plus full static/type/build gates pass.

## Evidence expectations

Record preflight, provider prerequisites without secrets, exact live command, run/checkpoint counts, before/after provider/status counts, sampled exact attribution/source records, personal-state safe checksums, unchanged call counts, and explicit limits. Never store raw provider payloads, credentials, private data, or image binaries.

## Explicit exclusions

No Trip Planner persistence/backfill, call refresh, map interaction/layout change, separate map-photo table, provider binary cache, or unrelated catalog cleanup.

## Progress and notes

- 2026-07-11: User explicitly authorized full catalog re-enrichment and Field Map inheritance.
- 2026-07-12: Focused resume investigation reconstructed the apparent completed-state loss from prior worker transcripts. Explicit operator SQL deleted 5 rows/reset counters, then deleted 426 and 423 completed rows and set processed checkpoints to 280 and 283 after the two logged 706-row snapshots. The final attempt added 28 rows before interruption, exactly reconciling the durable 311 processed and 1,078 lookup counts. DuckDB did not spontaneously lose the completed state.
- 2026-07-12: Repaired `run_catalog_photo_refresh` to recognize validated curated results for all current identities independent of run ID, return a database/network no-op for a complete current catalog, resume only missing identities, reconcile processed checkpoints monotonically, fail closed on a counter/result inconsistency, and derive completion from current valid rows. Added deterministic interrupted→resume and complete→rerun coverage. Focused catalog tests pass (17); ruff and diff checks pass. Mypy remains blocked by two existing errors in the untracked selector dependency. Evidence: `.10x/evidence/2026-07-12-catalog-photo-resume-root-cause-and-repair.md`.
- 2026-07-12: No live lookup or mutation was performed. Read-only state remains one failed run with 311 current curated rows (228 available iNaturalist, 83 curated unavailable), lookup count 1,078, and 395 missing current identities. Warehouse SHA-256 remained `da98954d69901d56584fae05e1c159027a9e7cdba8435b7f8b8e4f6b7a8cd7c1`.
- 2026-07-12: Applied the accepted final review repair by explicitly narrowing `_safe_qid` results into `list[str]` before join and P225 lookup, with no runtime/provider/DB semantic change. The 43 combined curated/catalog tests, focused two-module MyPy, Ruff, format, and diff checks pass; package-wide MyPy reached 56 files but remains environment-blocked only by eight missing `databox_sources` imports in unrelated orchestration-domain modules. The optional follow-up review was not rerun; the accepted two-error finding is resolved with no known blocker. Evidence: `.10x/evidence/2026-07-12-catalog-photo-resume-root-cause-and-repair.md`.
- 2026-07-12: User explicitly authorized resuming the remaining 395 current identities. Resume launched with corrected missing-only/no-op semantics and no manual SQL cleanup.
- 2026-07-12: Preflight passed the corrected 43-test/type/lint/format/diff/staging gates, proved exactly 311 valid current curated rows and 395 missing, found no other DuckDB writer, and captured a same-hash protected warehouse copy plus 86 protected table/subset fingerprints and external-state hashes.
- 2026-07-12: Launched exactly one `.venv/bin/python scripts/catalog_media.py --refresh-photos --batch-size 706` command. The execution harness terminated it at the 3,600-second tool timeout. It was not polled or rerun, and no manual SQL/counter change was performed. The durable checkpoint is 456 valid current curated rows, 250 missing, 373 available iNaturalist and 83 curated unavailable; run metadata is running/456 processed/1223 lookups. All 86 protected table/subset fingerprints are unchanged. Evidence: `.10x/evidence/2026-07-12-catalog-photo-live-resume-timeout-checkpoint.md`.
- 2026-07-12 retrospective: A live provider campaign paced at the approved request rate can exceed a one-hour harness call even for fewer than 400 identities. Future authorized continuation must use an execution window comfortably beyond the observed duration while retaining the single-command/no-poll/no-automatic-rerun controls. External termination can leave truthful row checkpoints with run metadata still `running`; do not repair that metadata manually because missing-only resume semantics reconcile it safely.

- 2026-07-12: User authorized the recommended single missing-only resume for the remaining 250 identities with a 150-minute command timeout.
- 2026-07-12: Final preflight proved 456 valid current curated rows, exactly 250 missing, no DuckDB writer, unchanged 86 protected fingerprints, and unchanged 19 external-state hashes. The authorized command launched exactly once with a 9,000-second tool timeout and completed: 706/706 valid current rows, zero missing, 621 available iNaturalist and 85 curated unavailable, run complete/706 processed/1,473 cumulative lookups. The original 456 identities were preserved and the lookup delta was exactly 250, proving no completed identity was queried again. All protected state remained unchanged after the run and full gates. Evidence: `.10x/evidence/2026-07-12-catalog-photo-final-live-resume-and-verification.md`. Review: `.10x/reviews/2026-07-12-catalog-photo-final-live-resume-review.md`.
- 2026-07-12: Full closure gates passed: 766 Python tests and three snapshots, Ruff/format, MyPy across 99 source files, 273 frontend tests, TypeScript, production build, bundle audit, secret scan, generators, diff, and empty staging. Review verdict is pass with no blocker.
- 2026-07-12 retrospective: WAL/checkpoint behavior makes the base DuckDB file hash insufficient for live mutation safety. Stable multiset fingerprints over every protected table/subset, captured before launch and rechecked after all gates, provide stronger semantic proof while avoiding exposure of private row contents. Pair that proof with the exact preflight identity set and lookup delta to distinguish a true missing-only resume from a superficially complete rerun.

## Blockers

None.
