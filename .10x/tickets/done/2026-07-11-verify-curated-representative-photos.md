Status: done
Created: 2026-07-11
Updated: 2026-07-13
Parent: `.10x/tickets/done/2026-07-11-upgrade-representative-bird-photos.md`
Depends-On: `.10x/tickets/done/2026-07-11-implement-curated-photo-selector.md`, `.10x/tickets/done/2026-07-11-migrate-catalog-and-map-curated-photos.md`, `.10x/tickets/done/2026-07-11-migrate-trip-planner-curated-photos.md`, `.10x/tickets/done/2026-07-12-repair-curated-catalog-refresh-ownership.md`, `.10x/tickets/done/2026-07-12-harden-trip-planner-curated-photo-resume.md`, `.10x/tickets/done/2026-07-12-repair-curated-photo-frontend-contracts.md`, `.10x/tickets/done/2026-07-13-implement-inaturalist-only-representative-photos.md`, `.10x/tickets/done/2026-07-13-migrate-inaturalist-only-representative-photos.md`, `.10x/tickets/done/2026-07-13-harden-inaturalist-photo-operations.md`, `.10x/tickets/done/2026-07-13-reconcile-inaturalist-photo-migration-evidence.md`

# Verify curated representative photos

## Scope

Aggregate verification of curated iNaturalist-only representative-photo selection, catalog/profile/map/planner integration, typed unavailable placeholders, live migration coherence, privacy/source boundaries, and accessibility. Run independent architecture, correctness, privacy/security/source, and UX/accessibility reviews after all implementation children are done.

## Acceptance criteria

- Every scenario in `.10x/specs/curated-inaturalist-representative-bird-photos.md` maps to recorded evidence.
- Full Python, frontend, strict TypeScript, production build, bundle audit, Ruff, formatting, MyPy, secret scan, diff checks, hooks, and relevant SQLMesh/non-mutating data gates pass.
- Tests make no live provider calls; any live evidence is limited to the explicitly authorized enrichment/backfill and bounded read-only post-migration inspection.
- Catalog, profile, Field Map, new planner, and saved planner photos use only validated curated providers or placeholders.
- No model call, email, routine refresh, AVONET refresh, or binary persistence occurred.
- Personal observations/Watches, calendar/outbox, calls, catalog facts, and unrelated warehouse/runtime state remain coherent and unchanged within recorded limits.
- Independent architecture, correctness, privacy/security/source, and UX/accessibility reviews pass or every finding is resolved with rerun evidence.
- Active specs, decisions, tickets, evidence, reviews, parent dependencies, and retrospective records are coherent before closure.

## Evidence expectations

Create aggregate evidence and four independent review records. Preserve command outputs or bounded summaries, exact counts, migration limits, and residual physical-browser/assistive-technology gaps. Do not claim visual perfection from metadata tests alone.

## Explicit exclusions

No new feature implementation, source expansion, manual visual moderation system, or unrelated repair. Out-of-scope findings require separate durable owners.

## Progress and notes

- 2026-07-11: Opened as aggregate gate for the ratified curated-photo change.
- 2026-07-12: All three implementation and migration children are done. Aggregate verification began against the active specification and recorded child evidence.
- 2026-07-12: All non-review aggregate gates passed: 769 Python tests/three snapshots/86.37% coverage, 273 frontend tests, strict TypeScript, production build/bundle audit, Ruff/format/MyPy, secret/generated/docs/source-layout checks, 13 SQLMesh tests, all 11 pre-commit hooks, diff, and empty staging. Read-only offline validation found 706/706 valid catalog results (621 available iNaturalist, 85 curated placeholders) and eight/eight valid singleton saved-planner results, with no separate map-media table. Every active-spec scenario is mapped in `.10x/evidence/2026-07-12-curated-representative-photo-aggregate-verification.md`. Four independent aggregate reviews remain before closure.
- 2026-07-12: Four independent reviews completed and all returned fail. Durable records: `.10x/reviews/2026-07-12-curated-representative-photo-architecture-review.md`, `.10x/reviews/2026-07-12-curated-representative-photo-correctness-review.md`, `.10x/reviews/2026-07-12-curated-representative-photo-privacy-security-source-review.md`, and `.10x/reviews/2026-07-12-curated-representative-photo-ux-accessibility-review.md`. Findings were split into four bounded repair tickets.
- 2026-07-13: The user superseded Wikimedia-first behavior after two safe WDQS failures and observed `invalid unavailable photo` in the built app. Aggregate verification now targets `.10x/specs/curated-inaturalist-representative-bird-photos.md`; historical Wikimedia aggregate evidence remains informative but cannot close the active contract.
- 2026-07-13: iNaturalist-only implementation closed with passing full gates and read-only proof that the current 706-row catalog returns HTTP 200 with safe placeholders rather than whole-response failure. Evidence: `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-implementation.md`.
- 2026-07-13: Serialized migration closed: catalog 706/706 strict results (622 available, 84 placeholders), saved planner eight/eight available, zero Wikimedia/GBIF representative rows, zero inserted calls, 86 protected fingerprints and 19 external hashes unchanged, and all post-migration gates passed. Evidence: `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-migration.md`.
- 2026-07-13: Non-review aggregate verification completed against the active iNaturalist-only specification. All ten scenarios map to exact tests/evidence. Fresh read-only reconstruction confirmed 706/706 catalog singletons (622 available, 84 placeholders), eight/eight planner singletons, zero legacy providers, zero-target/zero-lookup dry-run, HTTP 200 mixed-placeholder catalog/profile/map/plan/browser GETs with forbidden discovery, and unchanged DuckDB hash. Evidence: `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-aggregate-verification.md`.
- 2026-07-13: Four independent final rereviews completed. UX/accessibility passed. Architecture, correctness, and privacy/security/source failed on actual request-count/durable planner observability, retryable provider-failure recovery, cross-process/restart rate budget, 82 prior-run placeholder campaign ownership, and durable fingerprint artifact reproducibility. Reviews: `.10x/reviews/2026-07-13-inaturalist-only-final-architecture-review.md`, `.10x/reviews/2026-07-13-inaturalist-only-final-correctness-review.md`, `.10x/reviews/2026-07-13-inaturalist-only-final-privacy-security-source-review.md`, `.10x/reviews/2026-07-13-inaturalist-only-final-ux-accessibility-review.md`.
- 2026-07-13: Operational hardening repair closed with exact provider-request accounting, durable catalog/planner observability, cross-process/restart-safe local rate budgets, governed retryable failure recovery, removal of dormant GBIF representative-photo seams, 98 focused and 775 full Python tests, and passing static/security/hooks/SQLMesh gates. Evidence: `.10x/evidence/2026-07-13-inaturalist-photo-operations-hardening.md`; review: `.10x/reviews/2026-07-13-inaturalist-photo-operations-hardening-review.md` (pass).
- 2026-07-13: Campaign reconciliation repair closed. Exactly 82 prior-run terminal placeholders were adopted with zero provider requests; the authoritative run now owns all 706 rows and reconciles 706 processed, 624 lookups, 1,248 requests, and all outcomes. Sanitized fingerprint artifacts and procedure are durable; 86 protected fingerprints and 20 non-rate-ledger external hashes match. Evidence: `.10x/evidence/2026-07-13-inaturalist-photo-migration-reconciliation.md`; review: `.10x/reviews/2026-07-13-inaturalist-photo-migration-reconciliation-review.md` (pass).
- 2026-07-13: Final closure reviews all pass: architecture `.10x/reviews/2026-07-13-inaturalist-only-closure-architecture-review.md`, correctness `.10x/reviews/2026-07-13-inaturalist-only-closure-correctness-review.md`, privacy/security/source `.10x/reviews/2026-07-13-inaturalist-only-closure-privacy-security-source-review.md`, and UX/accessibility `.10x/reviews/2026-07-13-inaturalist-only-final-ux-accessibility-review.md`. Supplemental ignored `.log` evidence was renamed to repository-visible `.txt`; the updated manifest validates. Aggregate evidence now includes final operational and residual-limit closure. Retrospective learning: `.10x/knowledge/curated-photo-operation-invariants.md`.
- 2026-07-13: Acceptance criteria mapped in `.10x/reviews/2026-07-13-inaturalist-only-representative-photo-parent-closure-review.md`; ticket closed.

## Blockers

None. All dependencies, evidence, review gates, graph checks, and retrospective obligations are satisfied.
