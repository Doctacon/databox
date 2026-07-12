Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-repair-rufous-artwork-contract-test.md

# Rufous artwork contract test repair

## What was observed

The committed static theme test required `<svg className="brand-mark">` and `brand-wing`, but the current reviewed shell intentionally imports `./assets/rufous.png` and renders it as a decorative local image. The stale assertion failed before this repair; no catalog-summary change caused the failure.

The repaired test requires the exact local PNG import and image use, empty alternative text plus `aria-hidden="true"`, valid PNG signature, and a bounded non-empty asset. Existing protections remain: no remote CSS/image/font/script URL and no Pokémon, Pokédex, Mapbox, or Google Fonts string.

## Procedure and results

- `PYTHONDONTWRITEBYTECODE=1 UV_OFFLINE=1 .venv/bin/pytest -q tests/test_rufous_theme.py --no-cov -p no:cacheprovider` — 4/4 passed.
- Full network-blocked Python — 674/674 passed with three snapshots and 86.58% coverage.
- Frontend — 222/222 passed with typecheck and production build; the bundled PNG was emitted locally by Vite.
- Ruff and format checks passed; bundle audit found all server-only names and configured values absent.

## Limits

This was a contract-test-only repair. Artwork, UI, theme, and behavior were not changed. Independent review remains required before closure.
