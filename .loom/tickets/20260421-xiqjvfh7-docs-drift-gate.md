---
id: ticket:docs-drift-gate
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T18:00:00Z
scope:
  kind: workspace
links: {}
---

# Goal

Teach `scripts/generate_docs.py` a `--check` mode that diffs the committed
`docs/dictionary/` tree against what the generator would emit now, and wire
it into CI as a hard gate. A PR that adds a source without regenerating the
dictionary fails the check instead of silently shipping a stale site.

# Why

`docs/dictionary/` is derived from `transforms/main/models/**` and the Soda
contracts. It's checked in because MkDocs needs it on disk at build time.
There's no gate ensuring operators re-run the generator after touching a
model or adding a source — today's repo is proof: `usgs_earthquakes` landed
without a matching `docs/dictionary/usgs_earthquakes/` tree. The docs site
still builds (it's regenerated in CI), but the *committed* dictionary is
already behind the repo.

Drift is silent and compounds. A `--check` mode surfaces it on the PR that
caused it, and CI enforces it.

This is the same pattern `generate_staging.py` would benefit from — see
`ticket:scaffold-staging-codegen` — so establishing the `--check` convention
here is reusable.

# In Scope

- `scripts/generate_docs.py` gains `--check` (mutually exclusive with default
  write mode). Generates to a tmpdir, diffs against `docs/dictionary/`,
  exits 1 with a unified diff on mismatch, 0 on match.
- New CI job `docs-drift-check` in `.github/workflows/docs.yaml` (or
  `ci.yaml`) that runs `python scripts/generate_docs.py --check` before the
  site build step.
- Backfill the gap: regenerate and commit the missing
  `docs/dictionary/usgs_earthquakes/` and `docs/dictionary/usgs_earthquakes_staging/`
  trees as part of this ticket so the new gate goes green on merge.
- `docs/new-source.md` (or the source-layout checklist) mentions running
  `python scripts/generate_docs.py` as a required step.

# Out of Scope

- Extending drift-check to `scripts/generate_staging.py` — that's a separate
  ticket once the pattern is proven here.
- Moving the dictionary out of the repo (auto-generating in CI only). The
  MkDocs build expects it on disk and that's fine.
- Auto-regenerating in a pre-commit hook. CI gate is enough; local pre-commit
  adds latency and can be bypassed.

# Acceptance

- `python scripts/generate_docs.py --check` exits 0 against a clean repo
  after the backfill lands.
- Deleting one file under `docs/dictionary/` and re-running `--check` exits
  1 and prints a diff naming the missing file.
- CI job `docs-drift-check` runs on every PR; removing a dictionary file and
  pushing fails the job.
- `docs/dictionary/usgs_earthquakes/` exists in the commit that closes this
  ticket.

# Close Notes — 2026-04-21

`scripts/generate_docs.py` gains `--check`: renders into a tmpdir, diffs
against committed `docs/dictionary/`, exits 1 with a unified diff on drift,
0 on match. Extracted the render loop into `generate_into(target)` so both
the normal write path and the check path share one code path.

`.github/workflows/docs.yaml` got a pre-build "Check committed dictionary is
fresh" step that runs `--check` before notebook render or site build — so a
PR with stale docs fails fast.

`SCHEMA_DESCRIPTIONS` backfilled for `usgs_earthquakes` and
`usgs_earthquakes_staging`. Regenerated `docs/dictionary/`: 24 files total,
2 new trees (the earthquake schemas), 10 page rewrites across existing
schemas (trailing-newline drift from prior partial generations).

Negative case verified manually: deleting `docs/dictionary/index.md` and
re-running `--check` exits 1 with `Missing from repo (1): + index.md`.

`docs/new-source.md` walkthrough step 10 now calls
`uv run python scripts/generate_docs.py` with a note that the CI gate will
fail PRs that skip it.
