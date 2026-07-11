Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-10-implement-watched-bird-evaluator-and-reports.md, .10x/specs/watched-bird-matching-and-reports.md

# Watched-bird evaluator and deterministic reports

## What was observed

The shared Quack full-refresh path now calls a watched-bird evaluator only after every requested source succeeds, Quack cleanup/dedupe completes, and SQLMesh transformation returns successfully. A stable refresh hash makes the evaluator idempotent. Transform/source failure prevents evaluation; evaluator failure propagates after the successful transform rather than being hidden.

The runtime-owned `birding_alerts` schema persists bounded evaluation runs, per-watch activation watermarks, processed submission identities, decisions/diagnostics, deterministic reports, sanitized GLM traces, stable-UID event intent, and cancellation resolutions. No SQLMesh model owns these tables.

For each active watch, the evaluator:

- requires exact species code and activation generation;
- accepts only observations strictly after activation and no more than 48 hours old at evaluation;
- requires valid, reviewed, explicitly non-private Arizona evidence with bounded public location identity and finite coordinates;
- filters by Haversine distance inside the watch's 1–300-mile radius;
- deduplicates overlapping recent/notable/load rows by modeled source submission identity and never reprocesses a submission for the stable watch ID;
- clusters by public location ID with independent submission count, coherent newest-row metadata, and deterministic count/newness/distance/name/ID ranking capped at ten;
- selects the earliest future Arizona sunrise-centered two-hour window inside the five-day horizon; later better weather cannot postpone it;
- persists normalized weather status/caveats and a deterministic report even when weather or model enrichment is unavailable;
- optionally calls only `@cf/zai-org/glm-5.2` with strict schema, exact species/fact-hash grounding, bounded emphasis IDs, and only target identity, the confirmed public destination/distance/evidence, morning, weather, and caveats; personal watch-center name/coordinates and secondary clusters are absent from the schema, serialized prompt, and trace;
- atomically persists a complete watch outcome or none.

A qualifying newer submission updates one event intent with the installation/taxon-stable UID and incremented sequence. The intent carries the exact activation generation so stale cancellation handoffs cannot cancel a resumed/replaced activation. Superseded/cancelled/expired reports receive resolution timestamps. Accepted unexpired same-activation pause/delete handoffs become CANCEL intent. A same-generation pending REQUEST with no accepted active calendar event becomes terminal `suppressed` in the same transaction: sequence/method do not change and report, time, horizon, and location payload are cleared, making it structurally non-sendable to the downstream outbox. Stale, absent, expired, or already-pending-cancel events resolve as no-op, so pause followed by delete cannot increment cancellation sequence twice. Natural expiry clears event payload while retaining UID/sequence identity. Ninety-day cleanup removes resolved reports/runs/cancellation resolutions and clears terminal event payload, while preserving processed identities, activation state, and minimal event identity needed to prevent replay.

Read-only `GET /api/watch-evaluations`, `/api/watch-reports`, and `/api/watch-reports/{report_id}` expose strict bounded shapes. They query only local persisted state, reject malformed timestamps/relationships/JSON, duplicate cluster IDs, and empty/over-500-character caveats, suppress internal watch/generation/fact/model fields, and return safe errors without leaking malformed/private values. Historical reports are not incorrectly joined to a newer event intent.

## Procedure and results

### Focused evaluator, grounding, and orchestration

```text
uv run --no-sync pytest --no-cov -q \
  tests/test_watched_bird_evaluator.py \
  tests/test_cloudflare_workers_ai.py \
  tests/test_parallel_refresh.py
48 passed
```

The thirteen evaluator tests cover every principal rejection diagnostic, overlapping feed/load dedupe, independent cluster counts and ties, coherent public metadata, earliest morning, weather normalization, strict GLM grounding and personal-center prompt exclusion, processed identity persistence, refresh/submission replay, sequence/UID update, activation watermark, model degraded mode, outcome rollback/resume with original run start time, accepted cancellation, pause/delete pending-request suppression and replay, pause-before-match-commit race handling, stale-generation no-op, natural expiry, malformed persisted API JSON/timestamps/duplicate clusters/oversized caveats, and retention.

Cloudflare tests additionally prove strict `uniqueItems`, exact fact-hash/species grounding, personal watch-center schema rejection, confirmed-location-only evidence, inconsistent freshness/window rejection, and no parser/model fallback. Parallel-refresh tests prove success ordering, source/maintenance/transform failure suppression, and evaluator failure propagation after transform.

### Complete Python suite

```text
uv run --no-sync pytest -q --record-mode=none --block-network
362 passed; 3 snapshots passed; coverage 86.84%
```

No live response was recorded and network was blocked.

### Browser regression

```text
task app:check
122 Vitest tests passed
TypeScript typecheck passed
Vite production build passed
bundle audit passed: 3 configured names and 3 values absent
```

The evaluator adds no browser-triggered mutation or delivery behavior; existing Trip Planner, Arizona catalog, My Birds, and target planning remained green.

### Static, typing, privacy, and repository gates

```text
uv run --no-sync ruff check <changed Python/test files>
uv run --no-sync ruff format --check <changed Python/test files>
uv run --no-sync mypy packages/
uv run --no-sync python scripts/check_secrets.py .
.venv/bin/pre-commit run --files <ticket files>
git diff --check
all passed; MyPy checked 86 source files
```

## What this supports

- All active specification trigger, eligibility, novelty, clustering, morning, deterministic degradation, idempotency, activation cancellation, privacy, read API, transaction, and retention requirements have executable evidence.
- No SMTP socket, MIME, outbox retry, independent-source alert, GBIF/Xeno trigger, or browser evaluation surface was added.
- Model traces contain only status, sole model identity when grounded, fact hash, and timestamp; private source locations are nulled before candidate processing, and personal watch-center name/coordinates are absent from remote model schema/prompts/traces.

## Limits

- This ticket creates event intent only. RFC iCalendar/MIME, durable outbox, SMTP/TLS/retries, and accepted/cancelled status transitions remain owned by the dependent calendar/outbox and delivery tickets.
- Sunrise uses the deterministic NOAA approximation rather than a network astronomy service.
- Final independent adversarial review passed and is recorded at `.10x/reviews/2026-07-11-watched-bird-evaluator-and-reports-review.md`.
