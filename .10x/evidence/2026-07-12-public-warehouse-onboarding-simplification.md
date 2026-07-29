Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-simplify-public-warehouse-onboarding.md, .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md

# Public warehouse onboarding simplification

## What changed

The public path now leads a data engineer through five explicit stages:

1. understand the DuckDB/dlt/SQLMesh/Soda/Dagster purpose and modeling workflow;
2. evaluate offline with `task install` and `task ci`;
3. optionally configure credentials and build `data/databox.duckdb`;
4. inspect assets and modeled data through Dagster and the dictionary;
5. extend through the new-source, source-layout, and modeling-skill workflow.

README remains short, warehouse-first, and details-on-demand. Its two Mermaid diagrams and full annotation/taxonomy/ontology/CDM/SQLMesh skill chain are unchanged. The quickstart no longer copies `.env.example` after `task install`; it accurately states that `task install` conditionally creates `.env`, separates offline `task ci` from optional live `task full-refresh`, and describes Dagster as the inspection surface.

`docs/index.md` is now the data-engineer start page. It names Dagster as orchestrator and Quack as the single-DuckDB access/ownership mechanism rather than describing Quack as orchestration.

## Rufous content preservation

The exact 215-line Rufous command section formerly in `docs/commands.md` and exact 28-line trip-calendar section formerly in `docs/runbook.md` were moved unchanged into new stable `docs/rufous-operations.md`. The warehouse command reference shrank from 307 to 100 lines and the warehouse runbook from 137 to 113 lines.

The original pages remain at the same URLs and contain concise links to the new owner. Compatibility anchors preserve the former deep links:

- `commands.md#agent-evaluations`;
- `commands.md#rufous-local-birding-app`;
- `commands.md#bird-alert-delivery-operations`;
- `runbook.md#trip-plan-calendar-invitations`;
- `index.md#whats-here`;
- `index.md#architecture-decisions`;
- `index.md#regenerate`.

`tests/test_rufous_theme.py` now includes the new public Rufous owner in its naming/theme contract. `tests/test_docs_navigation.py` prevents removal of the three legacy docs-home fragments.

## Navigation

MkDocs navigation is grouped into Start, Warehouse, Extend, Operate, Rufous, and Architecture decisions. All pre-existing authored pages retain their file URLs; `docs/rufous-operations.md` is the only new public page.

## Validation

- Exact moved-section comparison: both saved source sections occur unchanged in `docs/rufous-operations.md` and no longer occur in their original pages.
- README/Taskfile parity assertions: required commands present, duplicate `cp .env.example .env` absent, and Taskfile conditional creation present.
- Local Markdown link scan: 28 authored root/top-level/ADR pages passed.
- Compatibility-anchor assertions: all seven former deep-link IDs are present; the three docs-home IDs were also confirmed in rendered `site/index.html`.
- README structure assertion: exactly two Mermaid diagrams retained.
- `.venv/bin/python scripts/generate_docs.py --check`: 20 generated dictionary files in sync.
- `.venv/bin/mkdocs build --strict`: passed. Material emitted its upstream MkDocs 2.0 informational warning and the existing generated-dictionary pages-not-in-nav listing; neither is a build error.
- `.venv/bin/pytest --no-cov -q tests/test_docs_navigation.py tests/test_rufous_theme.py tests/test_bootstrap.py`: 21 passed, four dependency deprecation warnings.
- `.venv/bin/ruff check tests/test_docs_navigation.py tests/test_rufous_theme.py`: passed.
- `.venv/bin/ruff format --check tests/test_docs_navigation.py tests/test_rufous_theme.py`: two files already formatted.
- `git diff --check`: passed.
- `git diff --cached --name-only`: empty.

## Limits

This is a documentation/navigation move only. No Task command, Rufous operation, warehouse behavior, provider, source, model, generated dictionary page, or runtime state changed. MkDocs wrote only the ignored `site/` build output.
