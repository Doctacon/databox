Status: done
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-10-implement-personal-bird-collection-storage-and-api.md

# Implement watched-bird evaluator and reports

## Scope

Implement runtime evaluator state, post-successful-full-refresh orchestration seam, exact eBird candidate matching, clustering/ranking, freshness-first morning selection, deterministic report, optional strict GLM 5.2 enrichment, event intent, and safe read API governed by `.10x/specs/watched-bird-matching-and-reports.md`.

## Acceptance criteria

- Evaluation runs only after all required source loads and SQLMesh succeed; independent/failed jobs and API/watch mutations evaluate zero times.
- Candidate rules enforce exact taxon, activation boundary, 48 hours, valid/reviewed/non-private/public coordinates, radius, and submission-identity novelty.
- Clustering/ranking/coherent metadata and earliest sunrise-centered window are deterministic; weather never postpones for a later day.
- Replay and overlapping source feeds/loads create no duplicate match/report/event intent; newer facts update stable UID and increment sequence.
- Deterministic bounded report persists and remains deliverable with explicit caveat on GLM failure; sole-model strict grounding and sanitized traces pass.
- Pause/delete creates cancellation intent only for accepted unexpired events; expiry creates none.
- Safe run/report API is read-only/network-free and exposes no private/raw/credential data; retention preserves dedupe state.

## Explicit exclusions

No MIME construction, SMTP socket, outbox retry worker, GBIF/Xeno trigger, independent-source alert, browser-triggered evaluation, or exactly-once delivery claim.

## Evidence expectations

Record successful/failed trigger seam, every rejection reason, dedupe/replay/feed overlap, clustering/ties/distance, sunrise/weather cases, model degraded path, transaction rollback, privacy scans, and orchestration/full-suite results.

## Progress and notes

- 2026-07-10: Ticket derives from active watch/matching/report and event-intent contracts.
- 2026-07-10: Implemented post-transform full-refresh evaluation, runtime run/activation/novelty/decision/report/trace/event/cancellation state, exact 48-hour public reviewed matching, deterministic clustering/ranking, earliest sunrise window, weather normalization, strict sole-model emphasis grounding with deterministic degradation, stable UID/sequence intent, read-only typed APIs, and 90-day resolved-history cleanup.
- 2026-07-10: Adversarial repair bound cancellation to exact activation generation, resolved superseded/cancelled/expired reports, added natural expiry and terminal payload minimization, persisted activation watermarks, hardened candidate/API/model trust boundaries, prevented historical reports from inheriting newer event state, and preserved original run start time across crash-resume. Evidence: `.10x/evidence/2026-07-10-watched-bird-evaluator-and-reports.md`.
- 2026-07-10: Independent-review repair makes unaccepted pending REQUEST intent terminal `suppressed` with unchanged sequence/method and no sendable payload, covers pause/delete/replay and pause-before-match race, removes every personal watch-center field and secondary cluster from the remote GLM schema/prompt/hash, and rejects API caveats outside 1–500 characters or duplicate cluster IDs.
- 2026-07-10: Focused evaluator/Cloudflare/orchestration tests passed 48/48; complete network-disabled Python suite passed 362/362 with three snapshots and 86.84% coverage; browser gate passed 122/122 plus typecheck/build/bundle audit; Ruff, formatting, MyPy (86 files), secret scan, hooks, and diff checks passed.
- 2026-07-11: Final independent review passed with no blocker or significant finding. Review: `.10x/reviews/2026-07-11-watched-bird-evaluator-and-reports-review.md`.
- 2026-07-11: Retrospective preserved generation-bound cancellation, pre-send suppression, personal-center prompt exclusion, and novelty/event retention invariants directly in the active specification and adversarial tests; no additional skill record is needed.

## Blockers

None.
