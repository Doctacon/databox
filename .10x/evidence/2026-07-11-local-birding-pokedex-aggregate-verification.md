Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-10-verify-local-birding-pokedex.md, .10x/tickets/done/2026-07-09-build-local-birding-pokedex.md

# Local birding Pokédex aggregate verification

## Scope and authority inspected

Aggregate verification read all active specifications and decisions, the parent plan, all six completed implementation children, the three completed aggregate repair children, their evidence, and their pass reviews. The repaired committed state includes `47d88bf` (Trip Planner eBird eligibility/remediation), `78493fb` (strict Trip Planner browser boundary), and `a643b80` (remaining browser timestamps/load states). Committed implementation was inspected across FastAPI registration, runtime schemas, Cloudflare model boundaries, browser clients/routes, watched evaluation, calendar/outbox, delivery transport, and explicit scripts.

The completed children are:

- personal collection storage/API;
- My Birds and profile controls;
- target-bird planning;
- watched-bird evaluator/reports;
- calendar/outbox;
- Proton Bridge delivery/operations;
- Trip Planner eBird evidence eligibility and saved-plan remediation;
- Trip Planner browser-boundary hardening;
- remaining browser timestamp and My Birds load-state hardening.

Every implementation and repair child is `done`, every recorded child review verdict is `pass`, and dependency paths are coherent. This verification did not send SMTP, invoke live inference/source APIs, run refresh/remediation, mutate application state, or alter the live warehouse.

## Full automated gates

### Python, offline evaluations, source tests, coverage

```text
uv run --no-sync pytest -q --record-mode=none --block-network
414 passed; 3 snapshots passed; coverage 86.33%
```

This includes DeepEval, source VCR/schema/idempotency, planner eligibility/remediation, strict browser-contract backend support, catalog, collection, target planning, watched matching, outbox, SMTP fake transport, API, privacy, rollback, concurrency, and retention tests. No live response was recorded.

### Browser and bundle

```text
task app:check
199 Vitest tests passed
TypeScript passed
Vite production build passed
bundle audit passed: 12 server-only names and 10 configured values absent
```

The tests cover Trip Planner, exact bounded runtime response validation, strict ISO calendar/time handling across target/bird/alert clients, safe client-owned error mapping, catalog/profile, My Birds failed-load versus successful-empty state, target plans, alert operations, direct/history navigation, focus, native controls/dialogs/disclosures, loading/empty/error/busy states, responsive CSS contracts, and media accessibility/safety.

### SQLMesh and Soda

```text
cd transforms/main && ../../.venv/bin/sqlmesh test
13 tests passed

cd transforms/main && ../../.venv/bin/sqlmesh diff prod
No changes to plan: project files match the prod environment

uv run --no-sync sqlmesh --paths transforms/main lint
passed

Soda static structure validation
25 contracts valid

Production ContractVerificationSession over all committed contracts
25/25 passed
```

The production Soda run and SQLMesh inspection left the warehouse hash unchanged.

### Layout, docs, hooks

```text
uv run --no-sync python scripts/check_source_layout.py
7/7 sources passed

.venv/bin/pre-commit run --all-files
all hooks passed

task docs:build
MkDocs strict build passed

uv run --no-sync python scripts/generate_docs.py --check
docs/dictionary/ is in sync (20 files)
```

The initial aggregate run found one stale generated type. The bounded repair was independently reviewed and committed as `6db35d9`: `bird_species_traits_sk` now renders `TEXT`. Follow-up verification confirmed the commit contains only the generated one-line correction plus its ticket/evidence/review records; the canonical freshness check and MkDocs strict build now pass.

## Live read-only warehouse reconciliation

The SHA-256 of `data/databox.duckdb` before and after network-disabled tests, SQLMesh/Soda reads, docs/hooks, safe scans, and targeted reconciliation was identical:

```text
2a916fb3f8f6e5269e73fda986366c88927eb8079f3f2c93af11639bf2bf2e0d
```

Safe aggregate results:

```json
{
  "catalog": {"taxa": 706, "species": 624, "hybrids": 82, "traits_available": 600, "traits_unavailable": 106, "unique_species_codes": 706},
  "avonet_rows": 10661,
  "catalog_public_aggregate_mismatches": 0,
  "top_public_location_tuples": 337,
  "top_public_tuples_without_exact_qualifying_public_row": 0,
  "planner_view_ineligible": 0,
  "saved_plans": 0,
  "persisted_ebird_evidence": 0,
  "persisted_ineligible_or_unmatched": 0,
  "plans_with_ineligible_or_unmatched": 0,
  "historical_incomplete_traces": 8,
  "personal_runtime_tables": 0,
  "target_runtime_tables": 0,
  "raw_avonet_staging_schemas": 0,
  "main_dlt_relations": 0
}
```

The repaired live warehouse has zero saved Trip Planner plans and zero persisted Trip Planner evidence, so there is no remaining ineligible or unmatched persisted eBird evidence and no plan containing it. The eligible planner view independently reports zero ineligible rows. Eight traces from incomplete historical invocations remain intentionally and are not children of a completed saved plan.

The current local warehouse has no `birding_personal` runtime tables and no target/watch/event/outbox history; those schemas initialize on first authorized mutation/evaluation. Therefore live cross-feature personal/watch/target/event identity cannot be witnessed from existing user state. Exact species-code identity, hybrid non-inference, transaction, replay, and relationship behavior are instead covered adversarially by the passing isolated database tests. The only current `birding_alerts` table is the bounded verification ledger.

## Privacy, credential, and delivery-ledger audit

A safe exact-value scan loaded ten configured sensitive values without printing them and checked 542 tracked files, 68 log files, three compiled bundle files, and warehouse bytes. Zero occurrences were found on every surface for configured eBird, Xeno-canto, Cloudflare, turbopuffer, SMTP username/password/CA path, organizer, or recipient values. The repository secret scan and compiled bundle audit also passed.

The durable SMTP verification ledger was read without printing any configured value:

```json
{
  "rows": 2,
  "kinds_exactly_test_email_and_test_invitation": true,
  "unique_kind_rows": true,
  "all_states_accepted": true,
  "all_safe_reasons_smtp_bridge_accepted": true,
  "sensitive_columns": []
}
```

This confirms exactly the authorized ledger records and does not resend either check. As governed, Bridge acceptance is not proof of inbox delivery or calendar rendering.

## Adversarial acceptance matrix

| Area | Evidence and result |
|---|---|
| Identity | Live catalog reconciles exact 706/624/82/600 with unique species codes. Tests prove exact taxon use across collection, targets, watches, reports, events, and retries; hybrids never inherit parents. |
| Privacy | Live catalog aggregates exactly equal valid/reviewed/non-private facts; all 337 top tuples map to exact qualifying public rows. Trip Planner model/lookup/persistence independently require valid/reviewed/non-private evidence and live persisted ineligible evidence/plans are zero. Personal locations, observation notes, watch centers, and target origins are intentionally available only through their authorized typed local APIs; tests and safe scans establish they are absent from unrelated/public APIs, model prompts, traces, logs, compiled bundles, and committed fixtures. Configured secrets/addresses/paths and arbitrary raw-model payloads are absent from responses, logs, traces, bundles, committed records, warehouse bytes, and the bounded ledger. |
| Side effects | Network-blocked suite passed. GET/startup/watch mutation no-send tests pass. Evaluation is full-refresh-success-only. Sender and verification are explicit scripts. No sender/remediation/refresh/model/source command ran; warehouse hash is unchanged and the two-row ledger did not change. |
| Idempotency | Tests cover observation/wishlist/watch idempotency, source overlap and watch novelty, stable refresh IDs, same-submission replay, event UID/sequence, outbox dedupe, SMTP verification ledger, reconciliation replay, and retention dedupe. |
| Concurrency | Tests cover browser global mutation serialization, DuckDB mutation locks, two-worker outbox claims, in-flight older acceptance vs newer sequence, concurrent reconciliation, and atomic sender claim. |
| Crash/rollback | Tests cover personal legacy migration, target schema/persistence rollback, evaluator outcome resume, event/outbox atomic rollback, claim expiry before/after send boundary, delivery unknown, canonical tamper rollback, and accepted-snapshot non-regression. |
| Accessibility/UX | 199 browser tests cover native labels, combobox, cards, pagination, disclosures, dialogs/focus trap, route focus/title/history, strict date/timestamp boundaries, failed-load versus true-empty state, loading/error/empty/busy text, announced alert reconciliation, fixed safe errors, strict no-partial-render response boundaries, alert confirmations, and responsive CSS. Residual visual risk is limited to no screenshot-based audit. |
| Architecture | One local DuckDB, no `main._dlt*`, no AVONET staging, SQLMesh prod diff clean, browser only through FastAPI, sole model constant `@cf/zai-org/glm-5.2`, no fallback, and generic loopback STARTTLS SMTP boundaries are enforced and tested. |

## Supported criteria

- Full 414-test network-disabled Python, 199-test frontend/type/build/bundle, SQLMesh tests/lint/prod diff, Soda structure/runtime contracts, source layout, hooks, secret/privacy scans, generated-dictionary freshness, and MkDocs strict build pass.
- Catalog, AVONET, privacy, architecture, side-effect, idempotency, concurrency, crash, accessibility, and bounded Bridge-ledger claims are supported by current raw observations and reproducible commands.
- All child reviews pass and no child residual risk lacks an explicit scope statement.

## Repaired aggregate rerun and review gate

The generated-dictionary blocker is resolved by reviewed commit `6db35d9`. The Trip Planner privacy/browser-boundary and remaining browser timestamp/load-state findings are resolved by reviewed commits `47d88bf`, `78493fb`, and `a643b80`; their completed tickets, evidence, and pass reviews were re-read before the applicable reruns.

Current read-only checks established:

```text
uv run --no-sync python scripts/generate_docs.py --check
passed: 20 files in sync

uv run --no-sync mkdocs build --strict
passed

focused pre-commit hooks for the committed dictionary repair
passed

warehouse SHA-256 before/after
2a916fb3f8f6e5269e73fda986366c88927eb8079f3f2c93af11639bf2bf2e0d

SMTP verification ledger
2 unique rows; exact email/invitation kinds; both accepted; safe reasons only
```

Post-`a643b80` rerun reconfirmed 414 network-disabled Python tests at 86.33%, 199 frontend tests plus TypeScript/build/bundle audit, repository secret scan, all hooks, 20-file dictionary freshness, MkDocs strict, source/layout generation checks, zero saved/persisted/ineligible Trip Planner evidence, the same eight incomplete-invocation traces, the exact bounded ledger, and the unchanged warehouse hash above.

No sender, refresh, remediation, model, source, or application mutation command ran. The warehouse hash and exact two-kind Bridge ledger remained unchanged throughout verification. The aggregate counts/matrix above supersede the pre-repair 408/125-test and three-plan state.

No unsupported implementation criterion remains. Fresh aggregate architecture, correctness, privacy/security/side-effect, and final UX/accessibility reviews all passed and are recorded under `.10x/reviews/2026-07-11-local-birding-pokedex-aggregate-*-review.md`. The automated-visual and absent-live-personal-state limits are explicitly accepted in the review records; neither weakens the tested local contract.

## Limits

- No live personal, target-plan, watch-match, event, or outbox rows currently exist, so live reconciliation for those feature-state relationships is limited to schema absence plus isolated adversarial tests.
- Automated accessibility/responsive verification does not include a screenshot or manual assistive-technology audit.
- SMTP ledger verification proves bounded local Bridge acceptance records only.
