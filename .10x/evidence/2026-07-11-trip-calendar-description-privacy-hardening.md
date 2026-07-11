Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-harden-trip-calendar-description-privacy.md, .10x/specs/trip-plan-calendar-invitations.md

# Trip-calendar description privacy hardening evidence

## What was observed

The pre-repair `HEAD` implementation was loaded from a temporary file and exercised against a temporary DuckDB plan fixture. Arbitrary email/recipient content, an API key, an HTTPS media URL, and a private Arizona coordinate pair all survived canonicalization and appeared in the unfolded/unescaped ICS description. The reproduction printed `survives=True` for email, credential, URL, and coordinates.

After repair, persisted field-plan and caveat inputs are decoded through bounded NFKC, HTML-entity, and at most two percent-decoding passes, then rejected on boundary-aware email/recipient, assigned or natural-label credential/token/key, HTTP(S), private-key, and coordinate-pair markers. Validation runs before installation/event/outbox state creation, in Pydantic payload validation, and again at ICS rendering. The API returns only fixed code `unsafe_calendar_content` and fixed message `Trip plan cannot be included in a calendar invitation`.

Adversarial tests cover mixed case, arbitrary spacing, direct/once/double-percent encoding, HTML encoding, field-plan and caveat sources, builder validation bypass, no-write state, accepted-update rollback, API redaction, ordinary prose boundaries, and unchanged UID/hash/sequence behavior.

The privacy follow-up reproduced four natural-label bypasses (`API key is supersecretvalue`, `Secret is supersecretvalue`, `Recipient is Alice Smith`, and `Attendee is private party`) plus signed-latitude/positive-longitude `-33.8688,151.2093` and unsigned `51.5074,0.1278`. The repaired marker branches accept either assignment punctuation or natural `is` syntax (while plain `key is` prose remains outside the natural-label branch). Coordinate classification rejects pairs with an explicit sign on either component or at least three fractional digits on both components. It also rejects any valid-range pair preceded by a case-insensitive `Coordinates`, `GPS`, or latitude/longitude label and a connector of at most 48 characters, regardless of integer/lower precision, sign, case, spacing, or separator style. Latitude/longitude labels accept slash, hyphen, ampersand, comma, and `and`; connectors accept indentation/newlines and the digit-bearing datum label `(WGS84)`, but cannot cross sentence/clause terminators (`;.!?`) or contain other digits. This catches `LAT & LON: 34, 112`, `Lat, Lon: 34, 112`, `GPS:\n  34, 112`, and `Coordinates (WGS84): 34, 112`, while preserving `Coordinates are unavailable; walk 1, 2 miles.`, labeled out-of-range examples, dates, unlabeled short decimal/integer lists, and ordinary prose.

## Procedure and results

- Pre-repair temporary-module reproduction from `git show HEAD:packages/databox/databox/trip_plan_calendar.py`: email `survives=True`; credential `survives=True`; URL `survives=True`; coordinate pair `survives=True` after RFC comma unescaping. Temporary files and database were outside the repository and removed. An initial import attempt failed before execution because the temporary module was not registered in `sys.modules`; the corrected reproduction registered it and passed.
- `UV_OFFLINE=1 .venv/bin/pytest -q tests/test_trip_plan_calendar.py --no-cov` — 41/41 passed.
- `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 .venv/bin/pytest -q --record-mode=none --block-network` — 477/477 passed, three snapshots passed, 86.52% coverage.
- `.venv/bin/ruff check packages/databox/databox/trip_plan_calendar.py packages/databox/databox/trip_plan_calendar_api.py tests/test_trip_plan_calendar.py` — passed.
- `.venv/bin/ruff format --check packages/databox/databox/trip_plan_calendar.py packages/databox/databox/trip_plan_calendar_api.py tests/test_trip_plan_calendar.py` — passed.
- `.venv/bin/mypy packages/databox/databox/trip_plan_calendar.py packages/databox/databox/trip_plan_calendar_api.py` — passed.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — typecheck passed; 221/221 tests passed; build passed; 12 server-only names and 10 configured values absent.
- `.venv/bin/python scripts/check_secrets.py .` — passed with no output.
- Follow-up direct marker probe — all four exact natural-label bypasses and both exact coordinate bypasses rejected; `versions 1.20, 2.40`, `list 1.5, 2.5`, `date 7/11/2026`, and `the key is near the oak` accepted.
- Follow-up `UV_OFFLINE=1 .venv/bin/pytest -q tests/test_trip_plan_calendar.py --no-cov` — 52/52 passed.
- Follow-up `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 .venv/bin/pytest -q --record-mode=none --block-network` — 488/488 passed, three snapshots passed, 86.52% coverage.
- Follow-up `.venv/bin/ruff check ... && .venv/bin/ruff format --check ...` — passed for the changed implementation and test files.
- Follow-up `.venv/bin/mypy packages/databox/databox/trip_plan_calendar.py packages/databox/databox/trip_plan_calendar_api.py && .venv/bin/python scripts/check_secrets.py .` — MyPy passed and the secret scan produced no findings.
- Follow-up `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — typecheck passed; 221/221 tests passed; build passed; 12 server-only names and 10 configured values absent.
- Remaining-blocker focused `UV_OFFLINE=1 .venv/bin/pytest -q tests/test_trip_plan_calendar.py --no-cov` — 61/61 passed, covering lower-precision/integer `Coordinates` pairs, mixed-case/spaced `GPS`, spaced `LAT / LON`, full latitude/longitude labels, builder bypass, unlabeled short lists, labeled invalid ranges, and ordinary prose.
- Remaining-blocker full `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 .venv/bin/pytest -q --record-mode=none --block-network` — 497/497 passed, three snapshots passed, 86.53% coverage.
- Remaining-blocker `.venv/bin/ruff check . && .venv/bin/ruff format --check .` and `.venv/bin/mypy packages/` — 151 files lint/format clean and 94 source files type-safe.
- Remaining-blocker `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — typecheck passed; 221/221 tests passed; build passed; bundle audit passed.
- Remaining-blocker `.venv/bin/python scripts/check_secrets.py . && .venv/bin/python scripts/generate_staging.py --check && .venv/bin/python scripts/generate_platform_health.py --check` — no secret findings; both generated-contract drift checks passed.
- Final connector repair `UV_OFFLINE=1 .venv/bin/pytest -q tests/test_trip_plan_calendar.py --no-cov` — 72/72 passed, including table-driven natural connector variants plus labels with no valid pair and invalid-range pairs.
- Final connector repair `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 .venv/bin/pytest -q --record-mode=none --block-network` — 508/508 passed, three snapshots passed, 86.53% coverage.
- Final connector repair `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy packages/` — 151 files lint/format clean and 94 source files type-safe.
- Final connector repair `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — typecheck passed; 221/221 tests passed; build and bundle audit passed.
- Final connector repair `.venv/bin/python scripts/check_secrets.py . && .venv/bin/python scripts/generate_staging.py --check && .venv/bin/python scripts/generate_platform_health.py --check` — no secret findings and both generated-contract drift checks passed.
- Structural label/connector repair `uv run pytest tests/test_trip_plan_calendar.py -q --no-cov` — 79/79 passed, including exact ampersand/comma labels, newline indentation, `(WGS84)`, `and`, clause/sentence termination, and invalid-range boundaries.
- Structural label/connector direct probe — all five exact label/connector variants rejected; semicolon/period-separated unrelated pairs and an invalid-range labeled pair accepted.
- Structural label/connector full `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 .venv/bin/pytest -q --record-mode=none --block-network` — 515/515 passed, three snapshots passed, 86.54% coverage.
- Structural label/connector `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy packages/` — 151 files lint/format clean and 94 source files type-safe.
- Structural label/connector `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — typecheck passed; 221/221 tests passed; build and bundle audit passed.
- Structural label/connector `.venv/bin/python scripts/check_secrets.py . && .venv/bin/python scripts/generate_staging.py --check && .venv/bin/python scripts/generate_platform_health.py --check` — no secret findings and both generated-contract drift checks passed.

No live SMTP, stage, or commit command ran. SMTP coverage used only the existing fake transport. The build regenerated ignored `app/dist` artifacts as expected; no production warehouse or external state was touched.

## What this supports

This supports that the aggregate exploit is reproduced, prohibited description content fails closed before durable invitation writes and before ICS output, API failures are redacted and fixed, accepted state rolls back unchanged, normal prose retains canonical identity behavior, and full Python/frontend/privacy gates remain green.

## Limits

The detector is intentionally bounded to the prohibited marker families and common encoded representations named by the ticket; it is not a general secret-classification system. Unlabeled unsigned coordinate pairs are treated as coordinate-shaped only when both components have at least three fractional digits; unlabeled lower-precision pairs remain accepted to avoid ordinary list/version false positives. Recognized coordinate labels remove that precision requirement only for valid latitude/longitude ranges. Independent privacy follow-up review remains required before ticket closure.
