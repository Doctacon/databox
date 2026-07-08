# Staging Codegen

The previous source-specific SQLMesh layout used generated `*_staging.stg_*`
models. The active CDM workflow now writes SQLMesh models directly under
`transforms/main/models/environmental_observations/`; no staging contracts are
currently active.

`python scripts/generate_staging.py --check` remains in CI as a harmless drift
gate for future forks that choose to add codegen-driven staging contracts. With
no `*_staging` Soda contracts present, it has nothing to regenerate.

If a future source needs a reusable staging boundary, add a Soda contract with a
`source_table` key and run `python scripts/generate_staging.py`. Prefer direct
raw references from CDM models unless the normalization is repeated, complex, or
serves as an intentional quality boundary.
