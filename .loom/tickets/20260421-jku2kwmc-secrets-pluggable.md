---
id: ticket:secrets-pluggable
kind: ticket
status: ready
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 2
depends_on: []
---

# Goal

Keep `.env` as the zero-friction default. Document and expose integration points so a forker can plug 1Password, HashiCorp Vault, AWS Secrets Manager, or Doppler without modifying `databox.config.Settings`. `docs/secrets.md` covers the contract and a worked example for at least one backend.

# Why

A real operator running the scaffold in production won't keep API keys in a plaintext `.env`. Today the setting-load path is Pydantic-BaseSettings → env vars → `.env` file. That is fine for local dev and fine for GitHub Actions (which inject env vars from repo secrets), but a forker adopting the scaffold commercially wants to know where the secrets boundary is and how to redirect it.

The answer is already latent: Pydantic settings classes accept custom secrets sources via `settings_customise_sources`. Document that contract, provide one worked example, and keep `.env` as the default — no code change, pure documentation and worked-example work.

# In Scope

- Audit current `Settings` class for all secret-bearing fields (API tokens, MotherDuck token)
- `docs/secrets.md`:
  - Default behaviour: env var → `.env` fallback
  - Extension contract: Pydantic `settings_customise_sources` (document signature, precedence rules)
  - One worked example in `examples/secrets/`: a 30-line 1Password-CLI-backed source that reads `op://vault/item/field` references from a `secret_refs.yaml` and resolves them on startup
  - Brief notes on Vault (`hvac` library), AWS Secrets Manager (`boto3`), Doppler CLI — without building them, just link to their Pydantic integrations
  - How to verify no secret leaks: `scripts/check_secrets.py` already exists; document how to extend its regex list for custom token formats
- Link `docs/secrets.md` from README + CLAUDE.md
- Update `scripts/check_secrets.py` to understand `op://`, `vault://`, `aws-secrets://` reference formats so they aren't flagged as plaintext secrets

# Out of Scope

- Building multiple first-class integrations (1Password only as worked example)
- Automated secret rotation
- KMS encryption of the DuckDB file (separate operational concern; note as follow-up)
- Replacing `scripts/check_secrets.py` wholesale

# Acceptance Criteria

- `docs/secrets.md` exists, linked from README and CLAUDE.md
- `examples/secrets/one_password_source.py` exists, is self-contained, and the doc explains exactly how to wire it into `Settings`
- The example can be mentally run without copy-pasting — code blocks are complete and executable
- `scripts/check_secrets.py` does not flag `op://vault/item/field` references as plaintext secrets
- No change to the default `.env` path — the scaffold still works zero-config for a new forker
- MkDocs strict build clean

# Approach Notes

- Pydantic v2 `settings_customise_sources` classmethod is the supported extension point — pin that in the doc, future-proof against v1 lingering mentions
- Keep the 1Password example to ~30 lines; use the `op` CLI rather than the SDK to avoid a Python dependency
- For forkers running in GitHub Actions, the simplest path is still "load env from repo secrets" — call that out explicitly so they don't over-engineer
- Link to Pydantic's docs rather than rewriting them

# Evidence Expectations

- Rendered `docs/secrets.md` in the deployed site
- Working `examples/secrets/one_password_source.py` that can be wired into `Settings` with minimal modification
- `scripts/check_secrets.py` passes against a file containing `op://` and `vault://` references (demonstrating allowlist works)
