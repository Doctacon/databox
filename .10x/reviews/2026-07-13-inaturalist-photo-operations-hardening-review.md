Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-13-harden-inaturalist-photo-operations.md`, iNaturalist selector/catalog/planner operational hardening diff
Verdict: pass

# iNaturalist photo operations hardening review

## Assumptions tested

- Selector lookup counts were not being mislabeled as HTTP request counts.
- A v2 failure could be retried without requerying terminal/completed identities.
- Provider failure remained safe presentation data without becoming a permanent checkpoint.
- Catalog and planner run state survived interruption and exposed bounded diagnostics without URLs, payloads, credentials, or personal data.
- The rate/day budget held across process restart and separate local processes without tests touching shared project state.
- Removing the GBIF representative-photo seam did not remove GBIF occurrence context or Xeno-canto call behavior.

## Findings

No blocker or significant finding remains.

- **Request accounting:** Each selector result carries a bounded 0/1/2 attempt count. Catalog and planner update request counters immediately after lookup, so an interruption before evidence commit still records actual attempts. Persistence checkpoint and outcome updates remain transactional with the owned photo row.
- **Retry semantics:** Budget/transport/schema results are strict typed unavailable rows marked retryable. Terminal identity and shortlist-exhaustion results remain valid completion. Both photo-only operators reconstruct the full persisted result; retry runs select retryable/invalid rows only and skip completed terminal rows.
- **Run observability:** Catalog `photo_runs` and planner `recommendation_photo_runs` persist status, timestamps, duration, target/processed/lookup/request counts, bounded outcomes, and safe failure. Tests challenge failure, resume, interruption, completion, and no-op transitions.
- **Budget safety:** `fcntl` locks a stable sidecar lock file while bounded JSON state is loaded and atomically replaced. The counter is reserved before transport, which is conservative under crash. Tests use `tmp_path`, coordinate separate Python processes, reconstruct a limiter after restart, and confirm no project rate-state artifact exists.
- **Source boundary:** Active backend/tests contain no GBIF representative-photo getter, lookup, candidate, cache-URL, or injection seam. GBIF occurrence-evidence planner/API tests still pass. Creative Commons parsing remains shared licensing functionality, not a media-source branch.
- **Scope and state:** No frontend, provider expansion, live provider, project DuckDB, model, email, refresh, call enrichment, or binary behavior was added. Full gates and empty staging passed.

## Verdict

Pass. The final architecture/privacy findings owned by this ticket are resolved with deterministic evidence and no scope expansion.

## Residual risk

The durable limiter is local-filesystem coordination, not distributed coordination across hosts. Remote availability/content remains outside Rufous control because only metadata and URLs are persisted. Conservative pre-transport reservation may consume budget for a request not sent after a process crash; this fails safe and clears on the next UTC day.
