Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-10-implement-personal-bird-collection-storage-and-api.md, .10x/specs/personal-bird-collection.md

# Personal bird collection storage and API

## What was observed

The local FastAPI process now owns a separate `birding_personal` runtime schema in the existing DuckDB file with four tables: observations, wishlist, watches, and side-effect-free watch cancellation requests. SQLMesh does not own these tables.

- Observation events use UUID identity, DATE grain, bounded optional location/notes, stable created timestamps, and UTC updated timestamps that strictly advance even when the injected wall clock is equal or regresses.
- Life-list membership is derived at read time with count and first/latest dates; deleting the last event removes membership.
- Wishlist and watch state are unique by exact eBird species code, idempotent, and independent from observations.
- Watches retain per-taxon Arizona center, timezone, 1–300-mile radius, active state, strictly advancing updated timestamp, private stable watch ID, and private opaque activation generation. Changed active replacements and resume replace the generation; identical replacements, pause, and paused edits preserve it.
- Pause/delete transactionally preserve a bounded cancellation-request tombstone deduplicated by watch ID, activation generation, and reason. Two pause generations remain distinct even under an equal wall clock. API output contains only species, reason, request time, and opaque request identity; downstream can inspect/consume it but this API performs no event/outbox/SMTP side effect.
- Existing runtime tables migrate in three crash-resumable transactions required by DuckDB's alter/mutate boundary: atomic column DDL, atomic identity/primary-key backfill, then atomic NOT NULL constraints. For each species, only the newest legacy cancellation maps to the current watch/activation tuple and its normal deterministic request ID; older and orphan legacy rows receive distinct deterministic synthetic watch/activation identities derived from their immutable legacy request IDs. Two-phase temporary primary IDs avoid update cycles, equivalent target conflicts dedupe, and non-equivalent current/orphan identity conflicts raise a narrow internal migration error that rolls back and maps to the bounded `database_unavailable` API response without internal values. Failed and conflicting phases remain repeatable.
- Every create/edit/resume that establishes active identity validates the exact current `birding_agent.arizona_species_catalog`; hybrids are accepted. Stored rows remain visible as explicitly stale after catalog removal and can still be paused or deleted, but stale resume fails safely.
- Collection mutations use one application lock plus explicit DuckDB transactions. Schema initialization and the mutation roll back together on failure.
- GETs use read-only connections and do not initialize tables. Typed responses expose only bounded intentional fields.

## API surface

- `POST/GET /api/observations`, `GET/PUT/DELETE /api/observations/{id}`
- `GET /api/life-list`
- `GET /api/wishlist`, `PUT/DELETE /api/wishlist/{species_code}`
- `GET /api/watches`, `PUT/DELETE /api/watches/{species_code}`, pause/resume actions
- `GET /api/birds/{species_code}/collection-state`

Permanent observation deletion requires explicit `confirm=true`. Invalid/stale identities, Arizona boundaries, radius, dates, extra fields, missing IDs, concurrent mutation, and database failures return safe errors without database details.

## Procedure and results

### Focused API and regression

```text
uv run --no-sync pytest --no-cov -q \
  tests/test_personal_collection_api.py tests/test_bird_catalog_api.py tests/test_api.py
44 passed
```

Seventeen focused tests cover empty no-write/no-network reads; two-event life-list derivation; stable created and strictly advancing updated timestamps under equal/regressing clocks; confirmed hard deletion; hybrid identity; wishlist/watch/observed independence; private stable watch and opaque generation semantics; two distinct pause-generation handoffs under one clock value; stale pause/delete versus rejected stale resume; downstream inspect/consume; multi-row legacy current/older/orphan cancellation identity preservation; newest-current deterministic dedupe; idempotent rerun; transactional DDL/backfill/mutation rollback and resume; conflicting current and orphan legacy identities with exact safe repeat responses and rollback; Arizona/radius/date/extra-field validation; mutation-lock conflict; schema constraints; and absence of downstream event/outbox/SMTP tables. Socket creation was disabled for collection reads and mutations.

### Complete network-disabled Python suite

```text
uv run --no-sync pytest -q --record-mode=none --block-network
324 passed; 3 snapshots passed; coverage 86.30%
```

No live response was recorded.

### Static, typing, secret, and diff gates

```text
uv run --no-sync ruff check <changed Python/test files>
uv run --no-sync ruff format --check <changed Python/test files>
uv run --no-sync mypy packages/
uv run --no-sync python scripts/check_secrets.py .
git diff --check
all passed; MyPy checked 82 source files
```

## What this supports

The ticket's schema, transaction, derived state, idempotency, stale identity, hybrid, privacy, no-network, no-downstream-side-effect, validation, bounded migration-conflict handling at every mutation entry point, busy/error, and complete Python regression criteria have executable evidence.

## Limits

- Browser presentation and deletion confirmation UI are intentionally deferred to the dependent My Birds ticket; this API requires explicit confirmation mechanically.
- Cancellation-request tombstones deliberately do not decide whether an accepted unexpired event exists. The evaluator/calendar child must conditionally resolve each request into cancellation intent or a no-op, then consume it transactionally.
- Final independent adversarial review passed and is recorded at `.10x/reviews/2026-07-10-personal-bird-collection-storage-and-api-review.md`.
