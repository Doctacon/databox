Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Target: .10x/tickets/done/2026-07-11-harden-trip-calendar-description-privacy.md
Verdict: pass

# Trip-calendar description privacy review

## Findings

Independent adversarial review initially found and drove repairs for natural `is` credential/recipient markers, unsigned/positive and low-precision coordinates, labeled integer pairs, natural connectors, ampersand/comma latitude-longitude labels, multiline indentation, WGS84 labels, and unrelated-number false positives.

Final review verified structural rejection of recipient/email, secret/token/key, URL, and valid coordinate payloads across LAT/LON variants, newline indentation, WGS84, natural connectors/dashes/`are`, and boundary ranges. Semicolon-separated unrelated number pairs, invalid ranges, and ordinary prose remain accepted. Validation runs before installation/event/outbox writes and again during direct ICS construction; API errors are fixed and redacted.

Final validation records 515 Python and 221 frontend tests plus lint, format, MyPy, typecheck/build, bundle audit, secret scan, and drift checks passing.

## Reopened aggregate regression and final follow-up

Later aggregate adversarial review reopened the same scope for URL forms, generic credential identifiers, spaced/IP/localhost email, punctuation-qualified recipients, and coordinate representations including unsigned/positive, labeled low-precision, cardinal, Unicode degree, natural connector, multiline, WGS84, and EPSG forms. Each bypass was reproduced, repaired, and retained as a regression.

The final independent pass verified all accumulated governed families at both pre-write and direct ICS boundaries. URL-shaped domains now fail closed without semantic/TLD guesses; normalized email and label assignments cover governed spacing/punctuation; coordinates use range-checked labeled numeric and structural cardinal parsing with bounded connectors. Benign incomplete/out-of-range and ordinary non-URL prose boundaries remain accepted.

Final evidence records 230 focused and 666 full network-blocked Python tests, 221 frontend tests, and all static/privacy gates passing with no live SMTP.

## Verdict

Pass. Original and reopened aggregate privacy blockers are resolved.
