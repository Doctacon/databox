---
id: ticket:scaffold-no-auth-flag
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T17:15:00Z
scope:
  kind: workspace
links:
  parent: ticket:add-usgs-earthquakes-source
---

# Goal

Add a `--no-auth` flag to `scripts/new_source.py --shape rest` so public-API
sources can skip:

- the API-key env var guard in the generated `source.py`
- the stale `.env.example` append

# Why

Friction point #4 + #5 in `ticket:add-usgs-earthquakes-source`. Three of the four
current sources use public endpoints (USGS NWIS, USGS Earthquakes); a stub that
assumes `API_KEY_<NAME>` is present ships `raise RuntimeError("API_KEY_X not set")`
that the operator must delete by hand. Same logic also appends `API_KEY_X=` to
`.env.example`, which is noise for no-auth sources.

# In Scope

- `new_source.py` gains `--no-auth` (only valid with `--shape rest`).
- Separate Jinja template for the no-auth variant (e.g. a second REST template
  file, or a conditional block in the existing one).
- `ensure_env_stub` is skipped when `--no-auth` is set.
- Tests: verify the no-auth stub does not raise on `API_KEY_X` and that
  `.env.example` is untouched.

# Out of Scope

- Reworking all existing no-auth sources (USGS NWIS, USGS Earthquakes) to match.
- Adding an OAuth or session-cookie variant — one flag at a time.

# Acceptance

- `python scripts/new_source.py foo --shape rest --no-auth` produces a
  `source.py` with no `API_KEY_FOO` reference.
- `.env.example` is unchanged after that command.
- Existing auth path (`--shape rest` without `--no-auth`) still appends the
  `API_KEY_FOO=` line.
- New tests pass.

# Close Notes — 2026-04-21

Added `--no-auth` flag gated to `--shape rest`. `new_source.py`:

- `render()` passes a `no_auth` bool into the Jinja context
- `ensure_env_stub` skipped when `--no-auth` is set
- rejects `--no-auth` with any non-rest shape (exit 2)

`scripts/templates/source/rest/source.py.j2` now branches on `no_auth`:
authenticated variant keeps `os` import + `API_KEY_<NAME>` guard; no-auth
variant drops them and emits a public-endpoint flow.

Added three tests — guard absence, flag-shape validation, syntactic validity.
17/17 `tests/test_new_source.py` green.
