Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/done/2026-07-12-repair-curated-catalog-refresh-ownership.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Curated catalog refresh ownership repair evidence

## What was observed

The ordinary catalog apply/refresh path now obtains representative photos only through the shared curated selector and accepts only validated `wikimedia_commons`, `inaturalist`, or typed `curated_photo` unavailable evidence. It no longer accepts a GBIF representative-photo getter or persists GBIF representative-photo results. Xeno-canto call enrichment remains separately typed and unchanged.

Two transition tests establish the ownership boundary:

- Starting from valid curated rows, ordinary `refresh` with curated source exhaustion replaces photos only with typed `curated_photo` unavailable rows while retaining separately typed Xeno-canto call rows.
- Starting from a deliberately legacy-typed GBIF photo row, ordinary `apply` detects the invalid completion and repairs it with a validated curated provider; zero GBIF representative-photo rows remain.

## Procedure and results

- `.venv/bin/pytest --no-cov -q tests/test_catalog_media.py::test_ordinary_refresh_never_reinterprets_curated_photos_as_gbif tests/test_catalog_media.py::test_ordinary_apply_repairs_legacy_gbif_photo_with_curated_owner tests/test_curated_photo.py` — 39 passed in 9.83 seconds.
- `.venv/bin/mypy packages/databox/databox/catalog_media.py` — passed; the guarded curated-provider source is narrowed explicitly before constructing `CuratedPhotoResult`.
- `.venv/bin/ruff format --check packages/databox/databox/catalog_media.py tests/test_catalog_media.py tests/test_bird_catalog_api.py` — three files already formatted.
- `.venv/bin/ruff check packages/databox/databox/catalog_media.py tests/test_catalog_media.py tests/test_bird_catalog_api.py` — passed.
- `git diff --check` — passed.
- Cached diff assertion — empty staging.

The checks used only temporary test DuckDB files and deterministic injected metadata. No live provider request, project DuckDB access, model, email, call refresh against real data, or binary-media operation occurred.

## What this supports

This supports the ticket's code/test criteria that supported ordinary catalog refresh cannot reinterpret curated results as GBIF, legacy GBIF representative rows are repaired through an explicit write path, curated source exhaustion remains a typed placeholder, Xeno-canto calls remain separate, and browser/GET paths were not changed.

## Limits

Full Python/API/frontend gates and project-state fingerprints are deferred to aggregate verification as directed. No live catalog refresh or project database mutation occurred. Provider availability and visual subject quality are outside this deterministic evidence.
