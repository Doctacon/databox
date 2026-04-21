---
id: ticket:fork-friendly-bootstrap
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T19:30:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 2
depends_on:
  - ticket:unify-config-surface
---

# Goal

Extract all `Doctacon/databox` URLs and bird/weather/streamflow project identity into a single `scaffold.yaml` file at repo root. Provide `task init` that takes a new project name + GitHub org/repo and rewrites every templated reference. A forker clones, runs `task init`, and has a branded project with three example sources that still work end-to-end.

# Why

Today the repo embeds its identity in many places: `README.md`, `mkdocs.yml` (`site_url`, `repo_url`), `docs/**` hyperlinks, ADR filenames, badges, issue templates if any, generator scripts that emit GitHub URLs, and the `pyproject.toml` project name. A forker either tolerates the Doctacon branding, hand-edits dozens of files, or gives up. None of those are what "ultimate starting scaffold" means.

The aim is a one-command rebrand, not a sterile neutered template. The three example sources stay, fully wired — they demonstrate the pattern. The forker renames the project and then deletes / replaces sources at leisure.

# In Scope

- `scaffold.yaml` at repo root declaring templated values:
  - `project.name` (currently `databox`)
  - `project.slug` (currently `databox`)
  - `github.org` (currently `Doctacon`)
  - `github.repo` (currently `databox`)
  - `docs.site_url` (currently `https://doctacon.github.io/databox/`)
  - `authors` (currently author list)
  - `license` (currently MIT)
- `scripts/bootstrap.py`:
  - reads `scaffold.yaml`
  - walks files matching `include:` glob patterns
  - does literal-token substitution (e.g. `{{ project.name }}` → `databox`)
  - source files keep the tokens; deployed state stores the rendered values
  - idempotent: running again with the same values produces no diff
  - writes substitutions back into source files (so this is a one-shot "make the repo match scaffold.yaml" operation, not a per-build rendering)
- `task init`: prompts for new values (or accepts `--name`, `--org`, etc.), updates `scaffold.yaml`, runs `bootstrap.py`, and commits on a fresh branch
- Templatise the existing URLs/identity across: `README.md`, `mkdocs.yml`, `docs/**`, `LICENSE`, `.github/workflows/*.yaml`, root `pyproject.toml`, generator scripts that emit GitHub URLs, `CLAUDE.md`
- `docs/template.md` explaining how to fork and rename (what changes, what stays)

# Out of Scope

- Deleting the three example sources (forker does this manually or via a separate `task rm-source` — not this ticket)
- Replacing `databox` as the Python package name (package stays `databox`; the template name is the *project* identity)
- Converting the repo into a `cookiecutter` template with Jinja markup in filenames (`{{cookiecutter.project_slug}}/`) — that breaks IDE tooling; literal-token substitution with an `init` script is cleaner

# Acceptance Criteria

- `scaffold.yaml` exists with the templated values enumerated above
- `rg -n 'Doctacon|doctacon\.github\.io' -g '!scaffold.yaml' -g '!CHANGELOG*'` returns only the `scaffold.yaml` file and rendered docs that read from it
- Running `task init --name weatherbox --org example-org --repo weatherbox` on a fresh clone produces:
  - `README.md` badges pointing at `example-org/weatherbox`
  - `mkdocs.yml` site-URL `https://example-org.github.io/weatherbox/`
  - `pyproject.toml` project name `weatherbox`
  - zero remaining references to `databox` in the user-visible surface (Python package name unchanged)
- Running `task init` twice with the same params is a no-op
- After `task init`, `task full-refresh` still runs all three example pipelines green
- `docs/template.md` explains the process and is linked from `README.md`

# Approach Notes

- Prefer explicit `{{ project.name }}` tokens in files over implicit match-replace; it makes it obvious which strings are templated
- In rendered state (post-init), the tokens are resolved and the files are plain — running `task init` again reads the current `scaffold.yaml` and re-renders, overwriting
- Use `ruamel.yaml` or similar for `scaffold.yaml` reads so a forker who hand-edits keeps their comments
- Avoid touching generated artifacts (`docs/dictionary/`, `docs/metrics.md` if auto-generated) — the generators should themselves read `scaffold.yaml` so regeneration picks up the new identity

# Evidence Expectations

- Demo: fresh clone + `task init --name weatherbox --org example-org` + `git status` showing the scoped rewrite
- `task full-refresh` green after rename
- Deployed-docs site link (if we test-publish under a different name, link it; otherwise screenshot-equivalent evidence in PR description)

# Close Notes

Verified on main 2026-04-21: `scaffold.yaml` present, `scripts/bootstrap.py` present, `task init` target wired, `docs/template.md` published. Deliverable landed during earlier scaffold-polish work; ledger reconciled during status audit.
