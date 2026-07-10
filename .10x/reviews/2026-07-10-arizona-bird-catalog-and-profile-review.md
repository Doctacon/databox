Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Target: .10x/tickets/done/2026-07-09-build-arizona-bird-catalog-and-profile.md
Verdict: pass

# Arizona bird catalog and modeled profile review

## Target

The read-only FastAPI and React implementation governed by `.10x/specs/arizona-bird-catalog-and-profile.md`, including review repairs and the user-ratified removal of unavailable global-range metrics from the profile contract.

## Findings

- Initial review correctly blocked closure because the active specification required global-range metrics that were absent from the governed AVONET source, catalog completeness was only upper-bounded, malformed client errors were not strictly validated, nullable inference could be misstated, source statuses were implicit, and route focus/title handling was incomplete.
- The user explicitly ratified removing global-range metrics from this profile contract rather than expanding the pinned AVONET source. The specification and UI now state the bounded source limitation directly.
- Final review verified independent API and client enforcement of exactly 706 unique taxa with 624 species and 82 hybrids, including adversarial rejection tests.
- Typed response allowlists, safe error handling, three-state inference, deterministic modeled source statuses, AVONET provenance, public-location privacy boundaries, and `(private)` access warnings match the active contract.
- Native History navigation, direct static fallback, back/forward behavior, document titles, and heading focus—including asynchronous profiles—are implemented and tested without a router dependency.
- GET endpoints remain read-only and network-free; live evidence recorded an unchanged warehouse hash, zero socket calls, and exact 706/624/82/600 reconciliation.
- Focused checks passed 27 Python API/planner tests and 72 browser tests plus TypeScript, production build, bundle audit, Ruff, MyPy, secrets, and hooks.
- The separately owned source-suite isolation defect was subsequently repaired; the complete network-disabled Python suite now passes 307/307 without cassette changes.

## Verdict

Pass. All ticket acceptance criteria map to implementation and recorded evidence.

## Residual risk

Responsive behavior is protected through native DOM semantics and deterministic CSS breakpoint assertions rather than a separate screenshot-based visual audit. This does not block the local product contract.
