# Forking Databox

Databox is designed as a *scaffold*, not a finished product. The three example sources (eBird, NOAA, USGS) demonstrate the pattern — they stay wired end-to-end after you fork, so you can see data flow through dlt → SQLMesh → Soda → Dagster → MkDocs on day one.

This page covers the one-command rebrand that makes the fork yours.

## The rename

```bash
task init -- \
  --name Weatherbox \
  --slug weatherbox \
  --org example-org \
  --repo weatherbox \
  --site-url https://example-org.github.io/weatherbox/ \
  --copyright-holder "Alice Example"
```

`task init` delegates to `scripts/bootstrap.py`, which:

1. Reads the current identity from `scaffold.yaml`.
2. Applies your overrides to compute a new identity.
3. Substitutes every recorded old value for its replacement across the files listed in `scaffold.yaml`'s `bootstrap.includes`.
4. Writes the new values back to `scaffold.yaml`.

Running it twice with the same arguments is a no-op.

## What gets rewritten

| File / glob | What changes |
| --- | --- |
| `README.md` | CI/docs badge URLs, site link, `# Databox` heading, prose brand mentions |
| `mkdocs.yml` | `site_name`, `site_url`, `repo_url`, `repo_name` |
| `pyproject.toml` (root) | Workspace name, description string |
| `LICENSE` | Copyright holder line |
| `CLAUDE.md` | Title + project-identity sentences |
| `docs/*.md`, `docs/adr/*.md` | GitHub hyperlinks, brand name mentions |
| `scripts/generate_docs.py` | `REPO_BLOB_URL` constant used in dictionary links |

Auto-generated files under `docs/dictionary/` are *not* rewritten directly — their generator reads the updated URL, so the next `python scripts/generate_docs.py` regenerates them with the new identity.

## What does NOT change

- **Python package name.** `packages/databox/` stays `databox`, because `from databox.config import …` imports appear in every source package. Renaming the Python package would cascade through every source, test, and Dagster wiring — far outside the scope of a one-command rebrand.
- **External dependencies.** `dagster-sqlmesh` continues to pull from the upstream fork. If you fork that too, edit `packages/databox/pyproject.toml` manually.
- **The three example sources.** eBird, NOAA, USGS stay as working examples. Delete them (or replace them) at your own pace — the layout lint (`python scripts/check_source_layout.py`) enforces the shape new sources must follow.
- **`.loom/` history.** The `.loom/` records document how this scaffold was built; they are historical artifacts, not project identity.

## Verifying the rename

After `task init`, run the full gates:

```bash
task ci                                # ruff + mypy + pytest + drift check
python scripts/check_source_layout.py  # every source still satisfies the layout
task verify                            # smoke full-refresh (DATABOX_SMOKE=1) — all three sources through Dagster
```

Then a sanity grep:

```bash
rg -n 'Doctacon|doctacon\.github\.io'  # should return only .loom/ history
```

If anything remains outside `.loom/`, either add the file to `scaffold.yaml`'s `bootstrap.includes` or edit it by hand and open an issue — the scaffold aims to keep `task init` comprehensive.

## Adding your own templated values

`scaffold.yaml` is editable. Add a new field under `project:` or `github:`, then teach `scripts/bootstrap.py` how to substitute it by extending `compute_substitutions`. The rule: substitutions must be *specific enough not to collide with Python identifiers*. Full URLs, qualified paths like `{org}/{repo}`, composite tokens like `{slug}-workspace`, and the capitalized brand name are all safe. Bare lowercase slugs are not.

## Deleting the example sources

Out of scope for `task init` — that command only renames. To remove a source:

1. Delete `packages/databox-sources/databox_sources/<source>/`
2. Delete `packages/databox-sources/tests/<source>/`
3. Delete `transforms/main/models/<source>/`
4. Delete `soda/contracts/<source>/` and `soda/contracts/<source>_staging/`
5. Delete `packages/databox/databox/orchestration/domains/<source>.py`
6. Remove any analytics models or contracts that reference it
7. Run `python scripts/check_source_layout.py` — should report no missing layout for the remaining sources

A dedicated `task rm-source <name>` wrapper is planned but not yet shipped.
