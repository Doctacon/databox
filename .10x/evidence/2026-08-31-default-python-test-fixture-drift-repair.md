Status: recorded
Created: 2026-08-31
Updated: 2026-08-31
Relates-To: .10x/tickets/done/2026-08-31-repair-preexisting-default-python-test-failures.md

# Default Python test fixture drift repair

## What was observed

The default network-blocked suite initially had three deterministic failures:

1. `tests/birding/test_birding_trip_planner.py::test_ebird_and_gbif_lookups_enforce_inside_boundary_and_outside_radius` returned no eBird rows. Its test rows are dated 2026-07-08, while the planner's production default clock had advanced to 2026-08-31; the rolling recent-evidence window correctly excluded them before the radius assertions ran. GBIF does not use that recent-date filter, confirming this was clock drift in the test fixture rather than radius expansion or SQL distance regression.
2. Two hydrated-public-catalog tests in `tests/rufous_media/test_public_wikimedia_media_ingest.py` built species fixtures that predated the current fail-closed public export contract. They omitted `taxonomic_category`, family/order, traits, and licensed-occurrence evidence. `build_public_assets` correctly rejected the first missing category before creating the hydrated fixture.

The repairs are fixture-only:

- The radius boundary test now injects `2026-07-31T12:00:00+00:00`, putting its 2026-07-08 observations inside the configured 30-days-back window while retaining the exact inside/boundary/outside/missing coordinate cases and the production lookup code.
- The hydrated catalog fixture now supplies exact species-rank taxonomy and complete minimal catalog metadata for Rufous Hummingbird and Elegant Trogon. It retains empty media/traits, zero licensed occurrence counts, and null latest occurrence dates rather than inventing evidence.

A comparison against the pre-layout `HEAD` test files confirmed these are the only test-body changes beyond their directory moves.

## Procedure and results

### Reproduction

```text
uv run pytest --no-cov --block-network \
  tests/birding/test_birding_trip_planner.py::test_ebird_and_gbif_lookups_enforce_inside_boundary_and_outside_radius \
  tests/rufous_media/test_public_wikimedia_media_ingest.py::test_loader_can_validate_against_hydrated_active_public_catalog \
  tests/rufous_media/test_public_wikimedia_media_ingest.py::test_hydrated_public_catalog_mismatch_fails_before_table_replacement -q
```

Result before repair: **3 failed**. The failures were the empty recent-eBird result and two unsupported-taxonomic-category errors.

### Focused verification

The same command after repair passed **3/3** in 1.76 seconds. The test retained these explicit assertions:

- eBird and GBIF each return only `inside` and inclusive `boundary` source records;
- the greatest returned distance remains approximately exactly `1.1132 km`;
- hydrated public output admits exact matching species identity;
- a wrong common name still raises `PublicMediaError` for production species identity before replacing the media table.

### Complete safe suite

```text
uv run pytest --block-network
```

Result: **1,498 passed**, **7 snapshots passed**, **85.00% coverage**, 28 warnings, 107.34 seconds. The network blocker remained enabled. No live provider or production-mutating command ran.

### Static and repository checks

```text
uv run ruff check tests/birding/test_birding_trip_planner.py tests/rufous_media/test_public_wikimedia_media_ingest.py
uv run ruff format --check tests/birding/test_birding_trip_planner.py tests/rufous_media/test_public_wikimedia_media_ingest.py
git diff --check
git diff --cached --name-only
```

Results:

- Ruff: passed.
- Format: both files already formatted.
- Diff check: passed.
- Staged-file scan: empty; no files are staged.

## What this supports

This supports every acceptance criterion in `.10x/tickets/done/2026-08-31-repair-preexisting-default-python-test-failures.md`:

- all three deterministic failures pass without weakening production filters or validators;
- the complete default network-blocked Python suite is green;
- no live provider call or production data mutation occurred.

It also upgrades acceptance criterion 5 of `.10x/tickets/done/2026-08-31-organize-root-tests-and-scripts-by-domain.md` from the previously recorded red baseline to a complete green default-suite result.

## Limits

- The separately ticketed USFWS source-layout contract mismatch is not part of this evidence and was not repaired here.
- The full suite proves current deterministic behavior under the network blocker; it does not exercise live providers, production DuckDB state, SQLMesh production plans, deployments, publication, or SMTP.
- This repair updates test fixtures only. It does not establish that historical dates remain current evidence indefinitely; instead, it makes the intended rolling-window scenario deterministic through an injected test clock.

## Fixture-representativeness review supplement

Follow-up review identified that `Hummingbirds` and `Trogons` were plausible family common names but were not representative of production public-export records, where family common names are nullable and these fixture rows should use `None`. The fixture now retains only the source-backed scientific family identities (`Trochilidae`, `Trogonidae`) and order names while setting both family common names to `None`. No runtime code, validator, species identity, taxonomy category, media, traits, or occurrence evidence changed.

Verification:

```text
uv run pytest --no-cov --block-network \
  tests/rufous_media/test_public_wikimedia_media_ingest.py::test_loader_can_validate_against_hydrated_active_public_catalog \
  tests/rufous_media/test_public_wikimedia_media_ingest.py::test_hydrated_public_catalog_mismatch_fails_before_table_replacement -q
```

Result: **2 passed** in 0.73 seconds.

```text
uv run ruff check tests/rufous_media/test_public_wikimedia_media_ingest.py
uv run ruff format --check tests/rufous_media/test_public_wikimedia_media_ingest.py
git diff --check
```

Results: Ruff passed, the file was already formatted, and the repository diff check passed. No file was staged, and no network/provider or production-mutating command ran.
