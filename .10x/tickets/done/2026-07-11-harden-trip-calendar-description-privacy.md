Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-evolve-product-into-rufous.md
Depends-On: .10x/tickets/done/2026-07-11-implement-trip-plan-calendar-invitations.md

# Harden trip-calendar description privacy

## Scope

Repair the aggregate privacy-review blocker in trip calendar canonicalization. Before any event/outbox mutation, fail closed when persisted field-plan or caveat text contains recipient/email, credential/token/secret-like material, media or arbitrary URLs, private coordinate pairs, or other prohibited payload named by `.10x/specs/trip-plan-calendar-invitations.md`. Preserve the bounded intended prose/target/weather/local caveat contract and RFC escaping.

## Acceptance criteria

- Injected email/recipient, credential/token/key, HTTP(S) media/arbitrary URL, and coordinate-pair markers never enter an ICS payload or persisted outbox.
- Failure occurs before event/intent/outbox/attempt writes and returns a fixed safe API error.
- Ordinary field-plan prose and allowed location/target/weather/caveat facts continue to produce the exact stable UID/hash/sequence behavior.
- Tests cover case/spacing/encoding variants, false-positive boundaries, rollback, API redaction, and existing full calendar/privacy suites.
- Independent privacy follow-up review passes.

## Explicit exclusions

No broad planner remediation, automatic content rewriting, new calendar fields, recipient/config changes, or live SMTP send.

## Evidence expectations

Record direct exploit reproductions before/after, rollback state, focused/full tests, and review.

## Progress and notes

- 2026-07-11: Reproduced the original aggregate exploit from the pre-repair `HEAD`: arbitrary email, credential, HTTPS URL, and private coordinate pair survived canonicalization into unfolded ICS description text.
- 2026-07-11: Added bounded NFKC/HTML/two-pass percent decoding and boundary-aware fail-closed checks for email/recipient, assigned credential/token/key, HTTP(S), private-key, and signed coordinate-pair markers in persisted field-plan/caveat text. Validation precedes installation/event/outbox writes and is repeated at payload and ICS-builder boundaries.
- 2026-07-11: Added exploit variants, false-positive boundaries, builder-bypass rejection, no-write assertions, accepted-update rollback, fixed API redaction, and stable UID/hash/sequence regression coverage. Focused calendar tests pass 41/41; full network-blocked Python passes 477/477 at 86.52%; frontend passes 221/221 plus typecheck/build/bundle audit; Ruff, format, MyPy, and secret scan pass. Evidence: `.10x/evidence/2026-07-11-trip-calendar-description-privacy-hardening.md`.
- 2026-07-11: Repaired privacy follow-up findings: natural `is` credential/recipient labels and signed-latitude or high-precision unsigned/positive-longitude coordinate pairs now fail closed. Exact persisted-input and builder-bypass regressions reject all reviewer examples; date, short version/list pairs, ordinary `key is` prose, and existing prose boundaries remain accepted. Focused calendar tests pass 52/52; full network-blocked Python passes 488/488 at 86.52%; frontend remains 221/221 with typecheck/build/bundle privacy audit; Ruff, format, MyPy, and repository secret scan pass. Evidence updated at `.10x/evidence/2026-07-11-trip-calendar-description-privacy-hardening.md`.
- 2026-07-11: Closed the remaining coordinate-label gap: valid-range pairs immediately labeled `Coordinates`, `GPS`, or `lat/lon` (including case, spacing, separator, integer, lower-precision, and sign variants) now fail closed regardless precision/sign. Unlabeled short numeric lists and labeled out-of-range examples remain accepted; unlabeled signed/high-precision detection is unchanged. Focused tests pass 61/61; full network-blocked Python passes 497/497 at 86.53%; frontend remains 221/221; repository-wide Ruff/format/MyPy, codegen drift, bundle audit, and secret scan pass.
- 2026-07-11: Replaced the coordinate-label connector enumeration with a bounded, digit/newline-free natural-text/punctuation connector (up to 48 characters), closing `are`, dash, `at`, `for site are`, mixed-case, and spacing bypasses before any valid-range pair. Table-driven tests reject connector variants and accept labels with no pair or only invalid-range pairs. Focused calendar tests pass 72/72; full network-blocked Python passes 508/508 at 86.53%; frontend passes 221/221; repository Ruff/format/MyPy, codegen drift, bundle audit, and secret scan pass.
- 2026-07-11: Structurally hardened coordinate labels and connectors after final review: latitude/longitude abbreviations now accept slash, hyphen, ampersand, comma, and `and`; bounded connectors accept newline indentation and `(WGS84)` while rejecting any path across `;.!?`. Exact reviewer bypasses fail before writes, and `Coordinates are unavailable; walk 1, 2 miles.` remains accepted. Focused tests pass 79/79; full network-blocked Python passes 515/515 at 86.54%; frontend passes 221/221; repository Ruff/format/MyPy, drift checks, bundle audit, and secret scan pass.
- 2026-07-11: Final independent privacy review passed all prohibited-marker, coordinate-variant, pre-write/ICS defense, false-positive, and API-redaction criteria. Review: `.10x/reviews/2026-07-11-trip-calendar-description-privacy-review.md`.
- 2026-07-11: Retrospective preserved every discovered bypass as table-driven regression coverage; the hardened implementation/evidence now teach the bounded validation procedure, so no additional record is needed.

## Blockers

None.
