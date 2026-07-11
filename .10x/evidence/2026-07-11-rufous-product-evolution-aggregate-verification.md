Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-verify-rufous-product-evolution.md, .10x/tickets/done/2026-07-11-evolve-product-into-rufous.md

# Rufous product evolution aggregate verification

## Scope and authority inspected

Verification inspected the parent and aggregate verification tickets; all seven Rufous implementation/repair child tickets; the active Rufous shell, catalog media, personal collection, and trip-plan invitation specifications; the four governing Rufous decisions including the Watch-only supersession scope; all seven child evidence records; and all seven child pass reviews. The completed child graph and dependency order are coherent. Independent aggregate architecture, correctness, privacy/licensing/security, and UX/accessibility reviews subsequently passed and are recorded under `.10x/reviews/`.

No live SMTP/provider/model/source call, refresh, media apply, remediation, app mutation, stage, or commit command ran. Network access was disabled for the complete Python suite and no command capable of live delivery or acquisition was invoked.

## Full verification gates

- `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 .venv/bin/pytest -q --record-mode=none --block-network` — 461/461 passed, three snapshots passed, coverage 86.51%.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — TypeScript passed; 221/221 Vitest tests passed; Vite production build passed; 12 server-only names and 10 configured values were absent.
- `cd transforms/main && ../../.venv/bin/sqlmesh test && ../../.venv/bin/sqlmesh diff prod`, followed by `.venv/bin/sqlmesh --paths transforms/main lint` — 13 SQLMesh tests passed, lint passed, and prod diff reported no changes.
- Production Soda `ContractVerificationSession` over every committed contract — 25/25 contracts passed.
- `.venv/bin/python scripts/check_source_layout.py` — 7/7 sources passed.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy packages/` — passed; 151 files formatted and 94 source files type-safe.
- `.venv/bin/python scripts/check_secrets.py .`, generated staging/platform-health checks, and `.venv/bin/python scripts/generate_docs.py --check` — passed; 20 dictionary files are current.
- `.venv/bin/mkdocs build --strict` — passed. The output contains only MkDocs Material's upstream MkDocs 2.0 warning and the existing list of dictionary pages omitted from explicit navigation.
- `.venv/bin/pre-commit run --all-files`, `git diff --check`, and the empty cached-diff assertion — all passed; no staged files.

## Read-only warehouse reconciliation

`data/databox.duckdb` SHA-256 before all verification and after every test, SQLMesh/Soda read, static gate, and read-only reconciliation was identical:

```text
805d6d929988bc7b01d08e89021f39d245074d9532ae42f27e9ca063bda9551b
```

`data/sqlmesh_state.duckdb` remained `c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93`.

Read-only aggregate results:

```json
{
  "catalog_taxa": 706,
  "media_rows": 1412,
  "distinct_media_taxa": 706,
  "valid_exact_photo_call_pairs": 706,
  "catalog_pair_mismatches": 0,
  "identity_hash_mismatches": 0,
  "photos": {"available": 524, "unavailable": 182},
  "calls": {"available": 600, "unavailable": 106},
  "binary_columns": 0,
  "wishlist_tables": 0,
  "observations": 0,
  "watches": 0,
  "watch_cancellation_requests": 0,
  "live_trip_calendar_tables": 0,
  "smtp_verification_rows": 2,
  "smtp_verification_unique_kinds": 2,
  "smtp_verification_all_accepted": true,
  "smtp_verification_all_safe_reasons": true,
  "smtp_verification_unknown_kinds": 0
}
```

All 1,412 persisted media rows reconcile to exactly one validated photo and call for every exact current taxon. The production persisted-result validator accepted all 706 pairs, which includes governed identity, source, URL/hash, license, attribution, selection, date, and payload validation. Schema inspection found no binary column. Hybrid/no-binomial zero-lookup and parent/history/common-name non-inference remain covered by the passing network-blocked adversarial suite.

Wishlist is absent from live schema and runtime/UI/API absence tests pass. Observation, life-list, and Watch independence is covered by the passing collection and browser suites; current live personal tables are coherently empty.

The live warehouse has no trip-calendar tables because no authorized trip invite has been sent. Fake-transport tests prove stable UID sequence 0/1 updates, concurrent deduplication/claims, ambiguity handling, explicit unknown reconciliation, 1/5/15 retry behavior, non-regressing accepted snapshots, and zero implicit sends from GET/startup/plan creation/replay. The pre-existing redacted SMTP verification ledger remains exactly two unique accepted rows (`test_email` and `test_invitation`) with safe reason `smtp_bridge_accepted` and no sensitive columns; verification sent nothing.

## Rufous shell and originality

Focused and full frontend/Python contracts pass for Rufous route/title naming, rust/teal/cream tokens, original inline SVG motif, loading/empty/error/unavailable/busy/success states, native controls and media semantics, visible focus, 44px controls, 320px responsive rules, long-text wrapping, reduced motion, non-color status, dialog/live/busy behavior, and technical-identity preservation. Exact static and bundle scans found no Pokémon asset/name/font dependency and no remote theme/font asset.

## Post-privacy-repair re-verification (`73aba8f`)

After commit `73aba8f` hardened trip-calendar description privacy, the complete aggregate verification was repeated with network access blocked. The network-blocked Python suite now passes 515/515 tests with three snapshots and 86.54% coverage. The frontend remains 221/221 passing with TypeScript, production build, and bundle audit green. SQLMesh remains 13/13 with lint and clean prod diff; all 25 production Soda contracts pass. Source layout, Ruff, format, MyPy, secret scan, generated staging/platform-health/docs checks, MkDocs strict, pre-commit, diff, and no-stage gates all pass.

A direct 34-case prohibited-description marker matrix was run against both persisted field-plan and caveat inputs. It covers direct and encoded email, recipient/attendee, credentials/tokens/private keys, HTTP(S), signed and unsigned coordinates, lower-precision/integer labeled coordinates, label/connector variants, HTML/percent encoding, and multiline/WGS84 forms. Every case failed closed before installation, event-intent, outbox, or outbox-attempt writes; the focused matrix passed 34/34 assertions. The matrix invokes enqueue only and no delivery function or SMTP transport. The live warehouse still has zero `birding_calendar` tables and the SMTP verification ledger remains exactly the same two unique accepted historical rows, so verification made zero live sends and zero live event/outbox writes.

Read-only media reconciliation remains exact: 706 catalog taxa, 1,412 rows, 706 distinct taxa and 706 valid exact photo/call pairs; photo counts are 524 available/182 unavailable and call counts are 600 available/106 unavailable. Pair, identity-hash, and binary-column mismatches remain zero. Wishlist is absent and personal observations, watches, and cancellation requests remain coherently empty.

The warehouse hashes before and after all post-repair verification were unchanged:

```text
805d6d929988bc7b01d08e89021f39d245074d9532ae42f27e9ca063bda9551b  data/databox.duckdb
c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93  data/sqlmesh_state.duckdb
```

No live SMTP/provider/model/source call, refresh, apply, remediation, stage, or commit command ran. Generated ignored build/documentation artifacts were preserved.

## Final aggregate verification (`d074463`)

The complete aggregate verification was repeated at committed `d074463` after all accumulated calendar-description privacy repairs. The network-blocked Python suite passed 666/666 with three snapshots and 86.58% coverage. A focused catalog media, recommendation media/backfill, Wishlist removal, trip calendar, trip privacy remediation, Rufous theme, and personal collection gate passed 317/317. The calendar suite alone passed 230/230 and contains 92 persisted-input pre-write cases plus 59 direct ICS-builder bypass cases spanning every accumulated email, recipient, credential, URL, encoding, coordinate, cardinal, degree-glyph, connector, WGS84/EPSG, range, and benign-boundary family.

Frontend TypeScript, 221/221 tests, production build, and bundle audit passed; 12 server-only names and 10 configured values were absent. SQLMesh passed 13/13 tests, lint, and a clean prod diff. All 25 production Soda contracts passed. Ruff and format checks passed for 151 files; MyPy passed for 94 source files. Secrets, seven-source layout, generated staging/platform-health/docs freshness, MkDocs strict, pre-commit hooks, diff, and no-stage gates passed.

Final read-only reconciliation returned the same live aggregate:

```json
{
  "catalog_taxa": 706,
  "media_rows": 1412,
  "distinct_media_taxa": 706,
  "valid_exact_photo_call_pairs": 706,
  "catalog_pair_mismatches": 0,
  "identity_hash_mismatches": 0,
  "photos": {"available": 524, "unavailable": 182},
  "calls": {"available": 600, "unavailable": 106},
  "binary_columns": 0,
  "wishlist_tables": 0,
  "observations": 0,
  "watches": 0,
  "watch_cancellation_requests": 0,
  "live_trip_calendar_tables": 0,
  "smtp_verification_rows": 2,
  "smtp_verification_unique_kinds": 2,
  "smtp_verification_all_accepted": true,
  "smtp_verification_all_safe_reasons": true
}
```

Hashes before and after all final verification remained:

```text
805d6d929988bc7b01d08e89021f39d245074d9532ae42f27e9ca063bda9551b  data/databox.duckdb
c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93  data/sqlmesh_state.duckdb
```

No delivery function, SMTP transport, provider/model/source call, refresh, apply, remediation, warehouse mutation, stage, or commit command ran. Independent aggregate reviews subsequently passed and the verification ticket is closed.

## Findings and residual risk

- **No blocker:** implementation, child records, automated gates, live catalog reconciliation, no-send ledger, and warehouse immutability all satisfy the executable aggregate criteria.
- **No review blocker:** independent aggregate architecture, correctness, privacy/licensing/security, and UX/accessibility reviews passed and are recorded under `.10x/reviews/`.
- **Residual, accepted by active media contract:** provider-hosted image/audio bytes can later disappear; Rufous persists validated metadata only and makes no durable delivery guarantee.
- **Residual, evidence limit:** automated responsive/accessibility checks do not include a physical-device, screenshot, or assistive-technology audit.
- **Residual, evidence limit:** fake SMTP and the historical two-row Bridge ledger prove state/acceptance boundaries, not inbox delivery or calendar rendering.
- **Residual, evidence limit:** live observation/watch/trip-invite state is empty/absent, so relationship behavior is established by isolated adversarial tests rather than populated live-state reconciliation.
