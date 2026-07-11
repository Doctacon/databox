Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-refresh-generated-bird-traits-dictionary.md

# Generated bird-traits dictionary refresh

## What was observed

The canonical documentation generator deterministically corrected exactly one governed generated field in `docs/dictionary/environmental_observations/dim_bird_species_traits.md`:

```diff
-| `bird_species_traits_sk` | `UNKNOWN` | missing (must_be=0), duplicate (must_be=0) | — |
+| `bird_species_traits_sk` | `TEXT` | missing (must_be=0), duplicate (must_be=0) | — |
```

No other generated dictionary page changed. No implementation, SQLMesh model, Soda contract, source, script, task checksum, or live warehouse content changed.

## Procedure and results

### Exact generation and diff guard

```text
uv run --no-sync python scripts/generate_docs.py
Generated 18 model pages + lineage + index under docs/dictionary/

bounded diff assertion
dictionary_diff_exact=UNKNOWN_to_TEXT_only
```

The assertion required exactly one removed and one added content line in the target file, with the exact `UNKNOWN` to `TEXT` change above.

An initial shell wrapper used unavailable bare `python` after generation and stopped before validation. It made no additional change. The corrected wrapper used `uv run --no-sync python` for every Python validation below.

### Freshness and strict docs build

```text
uv run --no-sync python scripts/generate_docs.py --check
docs/dictionary/ is in sync (20 files).

task docs:build
Generated 18 model pages + lineage + index under docs/dictionary/
MkDocs strict build passed

uv run --no-sync python scripts/generate_docs.py --check
docs/dictionary/ is in sync (20 files).
```

The install task's local checksum file was snapshotted and compared/restored after the docs task. Its final SHA-256 remains:

```text
93c8e0e45d281b2f1fdefb710dea32305ae26ee57d10a440f26c46c65c96313b
```

No generated `app-install` checksum remains.

### Warehouse and governed-source immutability

```text
live warehouse SHA-256 before aggregate verification and after this refresh:
b19332fbaa712bb54a401e4c8dee6b5aa6d16fddeb77dbb3067644093a3ab7ed

git diff --name-only -- packages transforms soda scripts
(no output)

git diff -- .task/checksum
(no output)
```

No source API, model inference, SMTP operation, AVONET load, SQLMesh apply, or warehouse write command ran.

### Repository checks

The complete pre-commit hook suite ran during `task docs:build` and passed. Focused hooks and `git diff --check` are rerun after this evidence/ticket update.

## What this supports

- The ticket's only product artifact is the canonical generated `UNKNOWN` to `TEXT` correction.
- Dictionary freshness and MkDocs strict build pass after the correction.
- The correction is derived from current reviewed SQLMesh/Soda metadata; it does not alter that metadata.
- Task checksums, source/model/contract files, and live warehouse state remain unchanged.

## Limits

Independent review passed and is recorded at `.10x/reviews/2026-07-11-generated-bird-traits-dictionary-refresh-review.md`.
