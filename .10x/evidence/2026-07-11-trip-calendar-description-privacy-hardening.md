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

### Reopened URL and credential-identifier regression

The reopened aggregate-review examples `www.private.example/nest.jpg`, `ftp://private.example/nest.jpg`, `private.example/nest.jpg`, `client_secret=`, `smtp_password=`, and `refresh_token=` were directly probed and all rejected. URL checks now cover arbitrary hierarchical URI schemes, `www.` hosts, and plausible bare DNS domain/path forms after the existing bounded normalization. Credential assignment checks classify separator-delimited and camel-case identifier components for secret/password/passwd/token/auth and API/private/access-key names; ordinary prose and lookalike assignments such as `author=Audubon`, `passwordless=true`, `tokenization=enabled`, `authentication=required`, and `monkey=nearby` remain accepted.

- `UV_OFFLINE=1 .venv/bin/pytest -q tests/test_trip_plan_calendar.py --no-cov` — 109/109 passed, including persisted pre-write rejection, direct ICS-builder bypass rejection, encoded variants, arbitrary schemes, bare/www forms, credential identifier variants, and benign boundaries.
- `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 .venv/bin/pytest -q --record-mode=none --block-network` — 545/545 passed, three snapshots passed, 86.56% coverage.
- `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy packages/` — 151 files lint/format clean and 94 source files type-safe.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — typecheck passed; 221/221 tests passed; build and bundle audit passed.
- `.venv/bin/python scripts/check_secrets.py . && .venv/bin/python scripts/generate_staging.py --check && .venv/bin/python scripts/generate_platform_health.py --check` — no secret findings and both generated-contract drift checks passed.

### Principled identifier, domain, and spaced-email repair

The final reopened repair classifies an assignment identifier only when it is followed by `=`, `:`, or natural `is`. Snake, kebab, and contiguous identifiers reject any occurrence of `secret`, `password`, `passwd`, `token`, or `credential`; API/private/access/auth markers reject when the same identifier also contains key/client/credential/secret/token/password material. This rejects the exact reviewer prefix/suffix examples and `client_secret is private-value` without treating standalone `access is limited` or `private access is limited` as credential assignments.

Bare domains now use an explicit bounded allowlist (`com`, `org`, `net`, `io`, `edu`, `gov`, `us`, `example`, `test`, `invalid`, `local`) with optional port and optional slash/path/query. Exact reviewer port, empty-path, and query variants reject, while unrecognized taxonomy/module suffixes in `genus.species/juvenile` and `package.module/function` remain accepted. Normalized email matching permits whitespace around domain dots and rejects the exact `field.user@example . com` bypass.

- `UV_OFFLINE=1 .venv/bin/pytest -q tests/test_trip_plan_calendar.py --no-cov` — 150/150 passed, including persisted pre-write rejection, direct ICS-builder bypass rejection, exact reviewer variants, all allowlisted TLDs, and named false-positive boundaries.
- `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 .venv/bin/pytest -q --record-mode=none --block-network` — 586/586 passed, three snapshots passed, at 86.56% coverage.
- `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy packages/` — 151 files lint/format clean and 94 source files type-safe.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — typecheck passed; 221/221 tests passed; build and bundle audit passed.
- `.venv/bin/python scripts/check_secrets.py . && .venv/bin/python scripts/generate_staging.py --check && .venv/bin/python scripts/generate_platform_health.py --check` — no secret findings and both generated-contract drift checks passed.
- `git diff --check` and staged-file inspection — diff clean and no staged files.

### Canonical punctuation, structural spacing, and coordinate parsing repair

The detection-only view now performs bounded NFKC/entity/percent decoding, maps all Unicode `Pd` dash punctuation to ASCII `-`, and removes whitespace around `. / : @ [ ]`. Persisted prose and ICS output are not rewritten. Email parsing covers DNS domains, localhost, bracketed IPv4, and bracketed IPv6 literals. Recipient and credential labels accept Unicode/ASCII dash connectors after canonicalization and one bounded parenthetical qualifier. Coordinate parsing accepts comma, semicolon, and slash separators, recognizes paired N/S and E/W suffixes, and applies numeric latitude/longitude range checks before classification.

Table-driven regressions exercise each form through persisted field-plan/caveat pre-write rejection and direct ICS-builder bypass rejection. Benign boundaries cover sentence-separated labels, out-of-range cardinal pairs, unlabeled fractions/short pairs, date/version/list prose, and existing credential/recipient lookalikes.

- `UV_OFFLINE=1 .venv/bin/pytest -q tests/test_trip_plan_calendar.py --no-cov` — 182/182 passed.
- `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 .venv/bin/pytest -q --record-mode=none --block-network` — 618/618 passed, three snapshots passed, 86.57% coverage.
- `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy packages/` — 151 files lint/format clean and 94 source files type-safe.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — typecheck passed; 221/221 tests passed; build passed; 12 server-only names and 10 configured values absent.
- Secret scan, source-layout check, staging/platform-health/docs drift checks, and all pre-commit hooks passed.
- `git diff --check` and cached-diff inspection passed; no files are staged.

### General URL shape, punctuation connector, and partial-cardinal repair

The final review bypasses are now rejected without a public-TLD or semantic prose allowlist. A URL-shaped domain uses a general syntactic 2–63 ASCII-letter TLD and requires a `www.` prefix, path, query, or port hostname cue. Unicode ideographic/fullwidth/halfwidth domain dots normalize to ASCII only in the detection view. Consequently `.xyz`, long general TLDs, Unicode-dot hosts, and formerly documented `genus.species/juvenile` / `package.module/function` URL shapes fail closed, while ordinary scientific names and module prose with spaces remain accepted. Recipient and credential labels recognize slash and semicolon connectors. Coordinate classification treats either a single N/S or E/W suffix as sufficient coordinate evidence after range validation.

- Direct exact probe — 9/9 reviewed URL/Unicode-dot/recipient/credential/partial-cardinal bypasses rejected; 4/4 ordinary scientific/module, fraction, and invalid-range boundaries accepted unchanged.
- `PYTHONDONTWRITEBYTECODE=1 UV_OFFLINE=1 .venv/bin/pytest -q tests/test_trip_plan_calendar.py --no-cov -p no:cacheprovider` — 201/201 passed, including persisted no-write and direct ICS-builder cases.
- `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --record-mode=none --block-network -p no:cacheprovider` — 637/637 passed, three snapshots passed, 86.57% coverage.
- Repository Ruff and format checks passed for 151 files; MyPy passed for 94 source files; secret scan, source-layout checks, staging/platform-health drift checks, and all seven source checks passed.
- Frontend typecheck, 221/221 tests, production build, and bundle audit passed; 12 server-only names and 10 configured values were absent.
- `git diff --check` and cached-diff inspection passed; no files are staged.

### Natural, degree, and separator-free cardinal coordinate repair

Coordinate parsing now recognizes `and` alongside comma, semicolon, and slash separators, permits an optional degree symbol after each numeric component, and has a separate separator-free pattern that requires paired N/S and E/W suffixes. Both paths retain numeric latitude/longitude range validation before classifying content as prohibited.

- Direct exact probe — `31.7 N and 110.8 W`, `31.7° N, 110.8° W`, and `31.7N 110.8W` rejected; four out-of-range and ordinary directional-distance boundaries accepted unchanged.
- Persisted-input regressions verify all three exact values fail before event, outbox, attempt, or installation writes. Direct Pydantic-bypass regressions verify the ICS builder independently rejects them.
- `PYTHONDONTWRITEBYTECODE=1 UV_OFFLINE=1 .venv/bin/pytest -q tests/test_trip_plan_calendar.py --no-cov -p no:cacheprovider` — 211/211 passed.
- Full network-blocked Python — 647/647 passed, three snapshots passed, 86.57% coverage. Frontend typecheck, 221/221 tests, production build, and bundle audit passed.
- Repository Ruff/format checks passed for 151 files; MyPy passed for 94 source files; secrets, source layout, seven source checks, and generated staging/platform-health drift checks passed.

### Structural paired-cardinal parser

The paired-cardinal branch no longer enumerates separators. It recognizes a latitude number, optional normalized degree glyph, N/S suffix, a bounded lazy 1–48-character connector of any content, a longitude number, optional normalized degree glyph, and E/W suffix. Degree-like `º`, `˚`, `⁰`, and `∘` forms normalize to `°` only in the privacy detection view. ASCII-letter boundaries after cardinal suffixes prevent words such as `northern` and `western` from being treated as suffixes. Latitude and longitude range validation remains authoritative before rejection.

- Direct matrix — 7/7 exact/future connector forms rejected (`and`, comma/degree, whitespace-only, ampersand, `to`, Unicode dash/`º`, pipe/`˚`); 4/4 out-of-range, incomplete-cardinal, ordinary directional-distance, and educational degree-symbol boundaries accepted.
- Persisted-input and direct ICS-builder matrices cover the same connector/degree variants and prove pre-write plus render-time rejection.
- Focused calendar suite passed 222/222; full network-blocked Python passed 658/658 with three snapshots and 86.58% coverage.
- Frontend typecheck, 221/221 tests, build, and bundle audit passed. Repository Ruff/format, MyPy, secrets, source layout, source checks, and generated drift gates passed.

The final structural revision permits digits, parentheses, colons, and newlines inside the same 48-character connector bound because strict N/S then E/W suffixes make the pair unambiguous. Direct probes reject `(WGS84 / EPSG:4326)`, multiline `EPSG:4326:`, and digit-bearing datum connectors. Persisted-input and direct-builder tests cover WGS84/EPSG forms. Incomplete pairs, out-of-range EPSG pairs, and a 49-character connector remain accepted. Focused tests pass 230/230; full network-blocked Python passes 666/666 with three snapshots and 86.58% coverage; frontend remains 221/221 and all static/privacy gates pass.

No live SMTP, stage, or commit command ran. SMTP coverage used only the existing fake transport. The build regenerated ignored `app/dist` artifacts as expected; no production warehouse or external state was touched.

## What this supports

This supports that the aggregate exploit is reproduced, prohibited description content fails closed before durable invitation writes and before ICS output, API failures are redacted and fixed, accepted state rolls back unchanged, normal prose retains canonical identity behavior, and full Python/frontend/privacy gates remain green.

## Limits

The detector is intentionally bounded to the prohibited marker families and common encoded representations named by the ticket; it is not a general secret-classification system. URL-shaped domain detection uses a syntactic 2–63 ASCII-letter TLD and a `www`, path, query, or port hostname cue; a bare unprefixed hostname without those cues remains accepted to avoid treating every dotted term as a URL. Credential identifiers are classified by bounded sensitive components/substrings while benign lookalikes remain covered by regressions. Unlabeled unsigned coordinate pairs remain coordinate-shaped only when both components have at least three fractional digits or either cardinal suffix is present; unlabeled lower-precision pairs without cardinal evidence remain accepted to avoid ordinary list/version/fraction false positives. Recognized coordinate labels remove the precision requirement only for valid latitude/longitude ranges. Independent privacy follow-up review remains required before ticket closure.
