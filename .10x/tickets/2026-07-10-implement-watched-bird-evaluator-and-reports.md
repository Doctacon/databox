Status: open
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/2026-07-10-implement-personal-bird-collection-storage-and-api.md

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

## Blockers

None.
