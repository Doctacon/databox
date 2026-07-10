Status: active
Created: 2026-07-10
Updated: 2026-07-10

# Watched-bird matching and reports

## Purpose and trigger

This specification governs deterministic evaluation of active watches after—and only after—the shared full parallel refresh and SQLMesh transformation both succeed. Independent source jobs, failed refreshes, API requests, watch mutations, and GETs MUST NOT evaluate or deliver alerts.

## Runtime state

Runtime-owned DuckDB tables MUST persist evaluator runs, per-watch activation watermarks, qualifying source identities, clusters, match decisions, reports, GLM traces, and downstream event intent. Stable IDs and uniqueness constraints MUST make replay idempotent. Modeled eBird submission identity, not load ID, is novelty authority; load IDs remain provenance.

The evaluator run MUST have a durable unique refresh/evaluation ID and completion state. One transaction per watch/taxon outcome MUST either persist the complete match/report/event intent or nothing. It must execute after Quack and SQLMesh release writer ownership through a controlled single-writer orchestration boundary.

## Eligibility and novelty

A candidate MUST:

- match the watch's exact species code;
- be strictly after that watch's latest activation/resume boundary;
- be no more than 48 hours old at evaluation time;
- be valid, reviewed, and non-private;
- have a public location ID and coordinates;
- fall inside the watch's 1–300-mile Haversine radius.

A source submission previously processed for that watch MUST NOT trigger again, even if it appears in another load/feed. Invalid, unreviewed, private, stale, pre-activation, outside-radius, wrong-species, and already-processed rows MUST be persisted only as aggregate/reason diagnostics where useful; no private name/coordinate may be persisted in alert-facing facts, logs, reports, or traces.

## Clustering and ranking

Cluster eligible rows by public location ID. Rank clusters by independent submission count descending, newest observation descending, distance ascending, location name, and location ID. The confirmed destination is the top cluster; ties are deterministic. Report at most ten public clusters. Location metadata comes from one coherent newest ranked public row.

## Morning selection

Create candidate two-hour windows centered on local Arizona sunrise for mornings within the five-day event horizon, beginning with the earliest morning after evaluation. Choose the earliest valid window. Weather MAY break a tie between equally fresh windows using lower precipitation then lower wind, but MUST NOT postpone to a later day for better weather. Missing weather selects the same earliest window and produces an explicit caveat.

## Report contract

Persist a deterministic report containing target identity, watch center/radius, confirmed public destination, distance, independent submission count, newest evidence time, other ranked public clusters, selected morning, weather status, evidence/model freshness, and caveats about recency, access, and non-guaranteed presence.

A fresh GLM report MAY enrich organization/wording using only that exact bounded fact payload and strict JSON Schema through `@cf/zai-org/glm-5.2`. It MUST NOT add bird facts, locations, access claims, or alternate evidence. If GLM is unavailable or invalid, the deterministic report remains deliverable and explicitly says model enrichment was unavailable. No alternate model is allowed. Traces MUST be sanitized and bounded.

## Idempotency and event intent

At most one active event intent exists per watched taxon. A new qualifying match updates the same stable UID, increments sequence, and slides the five-day horizon. Re-evaluating the same source identities and facts creates no duplicate report, event intent, or outbox request.

Pausing/deleting a watch creates a cancellation intent only when an accepted, unexpired event exists; matching itself does not send SMTP. Expired events end naturally.

## Observability and API

Persist run counts, decision reasons, degraded-report state, and safe errors. Read-only API/UI surfaces MAY show watch match status, latest report, candidate public locations, event intent, and model-degraded caveat. GETs are network-free and side-effect-free. Private/raw arbitrary fields and credentials MUST never enter responses.

## Retention

Resolved match/report/event history becomes eligible for deletion 90 days after terminal resolution. State required for novelty deduplication MUST be retained or compacted into a non-sensitive watermark/identity ledger so cleanup cannot recreate alerts. Unresolved downstream delivery state is governed by the delivery specification.

## Acceptance scenarios

- Successful full refresh evaluates once; a failed source or transform evaluates zero times.
- Same submission in recent/notable feeds or later loads triggers once per watch.
- Private/stale/pre-activation/outside-radius evidence has no effect and leaks no location.
- Two clusters rank deterministically and select the earliest sunrise window regardless of later better weather.
- GLM failure persists an explicit deterministic report and event intent with no alternate call.
- Replay creates no duplicates; a newer qualifying match updates stable UID/sequence intent.

## Explicit exclusions

No SMTP socket use, MIME/iCalendar transmission, GBIF/Xeno alert triggers, independent-source-job alerts, private evidence, arbitrary retrieved narrative, exactly-once email claim, or browser-triggered evaluation.
