Status: recorded
Created: 2026-07-15
Updated: 2026-07-15
Relates-To: .10x/tickets/done/2026-07-15-repair-source-dictionary-drift.md, .10x/evidence/2026-07-15-unified-source-contract-aggregate-verification.md

# Source dictionary drift repair evidence

## What was observed

Before repair, `scripts/generate_docs.py --check` failed on exactly one generated page: `docs/dictionary/analytics/platform_health.md`. It reported three missing external dependencies:

- `raw_ebird.region_stats`
- `raw_ebird.taxonomy`
- `raw_noaa.datasets`

Running the repository generator updated exactly that page. The resulting diff adds exactly those three dependency bullets and no other dictionary content.

## Procedure and results

- `.venv/bin/python scripts/generate_docs.py` — generated 18 model pages, lineage, and index; Git reported only `docs/dictionary/analytics/platform_health.md` changed under `docs/dictionary/`.
- `git diff -- docs/dictionary/analytics/platform_health.md` — three added dependency bullets only.
- `.venv/bin/python scripts/generate_docs.py --check` — passed: `docs/dictionary/ is in sync (20 files)`.
- `.venv/bin/mkdocs build --strict` — passed; wrote only the ignored `site/` build directory. The existing informational nav listing and upstream Material-for-MkDocs warning did not fail strict build.
- `.venv/bin/ruff check scripts/generate_docs.py` — passed.
- `.venv/bin/ruff format --check scripts/generate_docs.py` — passed; one file already formatted.
- Bounded assertion — each of the three required dependency bullets is present exactly once.
- Bounded changed-file assertion — `docs/dictionary/analytics/platform_health.md` is the only changed generated dictionary source file.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty; no files staged.

## What this supports

This supports every criterion in `.10x/tickets/done/2026-07-15-repair-source-dictionary-drift.md` and removes the generated-documentation blocker identified by aggregate verification.

## Limits

No provider request, source refresh, SQLMesh command/apply, shared warehouse connection/write, model call, email, or product/runtime action occurred. MkDocs wrote only ignored build output under `site/`. Aggregate verification and closure review remain owned by `.10x/tickets/done/2026-07-12-verify-unified-source-contract-and-ci.md`.
