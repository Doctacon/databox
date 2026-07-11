Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-apply-rufous-product-theme.md, .10x/specs/rufous-product-shell.md

# Rufous product theme verification

## What was observed

- The shell and route document titles display Rufous; the FastAPI display title is Rufous.
- Local CSS defines the governed rust-orange, teal/ocean, cream/gold, ink and semantic state tokens and applies them to navigation, planner, catalog/profile media, collection, target planning, dialogs, tables, controls and state surfaces.
- The header includes an original inline Rufous bird/device SVG motif. No remote font/theme asset or new dependency was added.
- Responsive rules cover two-column intermediate layouts and a single-column 320px-safe shell. Focus-visible, 44px controls, long-text wrapping, non-color status glyphs, high-contrast and reduced-motion rules are present.
- Repository/package/database/internal technical names remain unchanged. Current user-facing app, docs commands, API, SMTP verification and bird alert/calendar wording use Rufous.
- Follow-up review repair replaced the two remaining acting-product references in `docs/commands.md` (media proxying and cancellation enqueueing) with Rufous. The naming contract now rejects any standalone `Databox` word across the current user-facing shell files and commands documentation while retaining explicit assertions for stable package and database identities.

## Procedure

- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — 12 frontend files and 221 tests passed; production build completed; bundle audit found all 12 configured names and 10 configured values absent.
- `.venv/bin/pytest -q` — 461 tests passed with 86.51% coverage; three snapshots passed, including the strengthened Rufous product-brand leak scan.
- `.venv/bin/pytest --no-cov -q tests/test_rufous_theme.py` — all 4 focused naming/theme contract tests passed.
- `.venv/bin/ruff check tests/test_rufous_theme.py && .venv/bin/ruff format --check tests/test_rufous_theme.py` — focused lint and format checks passed.
- `.venv/bin/pytest --no-cov -q tests/test_trip_plan_privacy_remediation.py tests/test_audit_app_bundle.py tests/test_bird_alert_delivery.py tests/test_bird_alert_outbox.py` — 51 focused privacy, bundle and alert-delivery tests passed.
- `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy packages/` — passed; 151 files formatted and 94 source files type-safe.
- `.venv/bin/python scripts/check_secrets.py . && .venv/bin/python scripts/generate_staging.py --check && .venv/bin/python scripts/generate_platform_health.py --check` — secret scan passed; generated SQL checks matched.
- `.venv/bin/python scripts/generate_docs.py && .venv/bin/mkdocs build --strict` — generated 18 model pages plus index/lineage and built documentation successfully.
- `.venv/bin/pre-commit run --all-files` — all hooks passed on the final rerun.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty; no files staged.

## What this supports

This supports the ticket acceptance criteria for naming, token/component/route/state coverage, responsive and accessibility CSS contracts, reduced motion, local original artwork, no remote theme assets, regression safety, privacy, bundle safety and documentation integrity.

## Limits

Verification is automated and screenshot-free as required. Browser CSS layout and platform-native audio rendering were not visually inspected on physical devices; their contracts are covered by DOM/static scans, semantic controls and responsive CSS rules.
