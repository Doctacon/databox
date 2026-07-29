Status: done
Created: 2026-07-12
Updated: 2026-07-12

# Warehouse repository simplicity audit

## Question

How can Databox become intuitive for data engineers while preserving all
warehouse and Rufous behavior and limiting cleanup to proven dead or duplicate
surfaces?

## Sources and methods

Read-only inspection covered:

- `README.md`, `mkdocs.yml`, all authored top-level `docs/*.md`, generated-doc
  ownership, and package README guidance;
- `Taskfile.yaml`, `.gitignore`, tracked root inventory, script references, and
  Git history for suspected generated/dead files;
- root and package `pyproject.toml` files, source-level imports between
  `databox` and `databox_sources`, canonical registry consumers, config,
  orchestration, quality, schema/CDM/SQLMesh/Soda boundaries;
- active source-registry, source-verification, modeling-completeness, and cleanup
  records;
- Rufous only where it crosses public commands/runbooks or consumes warehouse
  state.

Commands were bounded to `git ls-files`, `git status`, `git check-ignore`,
`git log`, `git blame`, `find`, `rg`, `wc`, `file`, `du`, `sed`, and `awk`.
No tests, builds, generators, imports, providers, SQLMesh, or warehouse commands
were run.

## Current newcomer path

The shortest coherent data-engineer path should be:

1. **Understand:** root `README.md` — local DuckDB warehouse, dlt ingestion,
   governed annotation/taxonomy/ontology/CDM workflow, SQLMesh, Soda, Dagster.
2. **Evaluate offline:** `task install`, then `task ci`; no provider or
   warehouse refresh is required to assess the implementation.
3. **Configure/build data:** edit the `.env` created by `task install`, then run
   `task full-refresh` only when source credentials and live ingestion are
   intended.
4. **Inspect/operate:** `task dagster:dev`, generated dictionary/lineage, and the
   warehouse operations runbook.
5. **Extend:** `docs/new-source.md` → `docs/source-layout.md` → the four modeling
   skills → contracts and generated dictionary.

The repository contains every component, but public guidance does not currently
present this path cleanly. README runs `task install` and then redundantly copies
`.env.example` over the `.env` that `task install` already creates. `docs/index.md`
still says the root README is a large case study and describes orchestration as
“Quack-backed local DuckDB,” while the canonical architecture says Dagster
orchestrates and Quack is the DuckDB transport/ownership boundary.

## Findings and candidates

### 1. Clarify and consolidate the public warehouse path

**Classification:** consolidate/clarify. **Confidence:** high.

Evidence:

- `README.md` is intentionally short and warehouse-first, but its quickstart
  duplicates `.env` creation already encoded in `Taskfile.yaml:install` and
  jumps directly to a live full refresh without distinguishing offline
  evaluation from credentialed ingestion.
- `docs/index.md` contains stale prose about the former large README and does
  not expose a start-here path for running or extending the warehouse.
- `docs/commands.md` is 307 lines; its Rufous section begins at line 57 and
  dominates the command reference through bird alerts, media, privacy
  remediation, collection, and delivery operations. Warehouse CLI guidance
  resumes only at SQLMesh near line 251.
- `docs/runbook.md` mixes warehouse rebuild/SQLMesh recovery with a detailed
  trip-calendar delivery procedure.
- `mkdocs.yml` exposes 18 authored pages as one mostly flat navigation list,
  although the content already separates warehouse concepts, extension,
  operations, and architecture.

Recommended slice:

- correct README quickstart to show offline evaluation versus optional live
  warehouse build without duplicating `.env` creation;
- make `docs/index.md` the data-engineer start page and remove stale README
  characterization;
- move Rufous-only command/runbook material, without rewriting semantics, to a
  dedicated Rufous operations page; leave concise links in warehouse commands
  and runbook;
- group MkDocs navigation into Start, Warehouse, Extend, Operate, Rufous, and
  Architecture while preserving every existing page/URL where possible.

Preservation checks: local-link/static documentation checks, strict MkDocs,
exact moved-section comparison, README command agreement with Taskfile, and
Rufous theme/documentation tests that inspect `docs/commands.md`.

### 2. Remove tracked/runtime repository noise

**Classification:** delete/ignore. **Confidence:** high.

Evidence:

- `.task/checksum/install`, `install-dev`, and `install-orchestration` are tracked
  Task runtime checksums. A later Task invocation generated the untracked
  `.task/checksum/app-install`, demonstrating that this directory is a mutable
  local cache rather than source authority. No project file consumes committed
  checksum contents.
- `.pi-subagents/` is not ignored and currently contains about 2.7 MB of local
  worker inputs, outputs, transcripts, and metadata. It repeatedly appears as
  untracked state and is not project source.
- `.deepeval/` is an unignored empty runtime directory, while Taskfile and tests
  explicitly route DeepEval cache to ignored `.cache/deepeval`.
- `.pi/skills/`, `.schema/`, `.10x/`, and `docs/dictionary/` are different:
  they are tracked authorities or generated artifacts with explicit contracts
  and must remain.

Recommended slice: untrack `.task/checksum/*`; ignore `.task/`,
`.pi-subagents/`, and `.deepeval/`; do not delete the tracked Pi skills,
modeling artifacts, durable records, or generated dictionary.

Preservation checks: `git check-ignore` assertions, clean Task invocation in a
temporary worktree or controlled local run, no tracked-path loss outside
`.task/checksum`, and existing install/Task tests if present.

### 3. Break the package metadata dependency cycle

**Classification:** delete duplicate dependency edge. **Confidence:** high.

Evidence:

- `packages/databox/pyproject.toml` correctly depends on `databox-sources`
  because Dagster domain modules import all seven `databox_sources.*` builders.
- `packages/databox-sources/pyproject.toml` also declares a runtime dependency on
  `databox`, creating a package metadata cycle.
- Static source inspection found no `databox` import in
  `packages/databox-sources/databox_sources/**`; reverse imports occur only in
  source-package tests that intentionally exercise canonical Dagster builders
  from the workspace package.
- The workspace root already installs both packages for repository tests.

Recommended slice: remove only the `databox` runtime dependency from
`databox-sources`, regenerate the lockfile, and document the one-way runtime
boundary: source definitions are independently importable; `databox` composes
them. Keep the two-package layout—collapsing packages is not evidence-backed.
Also correct the `databox` package description from deleted “quality engine” to
current quality/codegen tooling.

Preservation checks: lockfile coherence, import `databox_sources` without
`databox`, isolated source-profile tests, canonical builder tests, Dagster
definition loading, and full static/test gates.

### 4. Delete the superseded standalone smoke runner

**Classification:** delete. **Confidence:** high.

Evidence:

- `scripts/smoke.py` has no exact Taskfile, CI, docs, package, or test consumer.
- It constructs a second in-process `Definitions` object and executes all dlt
  assets plus SQLMesh directly.
- Canonical smoke/full behavior is now `task verify` / `task full-refresh` via
  `scripts/load_dlt_quack.py` and the reviewed parallel-refresh lifecycle.
- `packages/databox/databox/config/sources.py` still names `scripts/smoke.py` in
  its module docstring, making the dead path appear authoritative.

Recommended slice: delete `scripts/smoke.py` and repair the registry docstring.
Do not replace it with another wrapper.

Preservation checks: exact reference scan, source registry tests, parallel
refresh/source runner tests, Dagster definition loading, and `task verify`
command-shape inspection. Do not execute a live verify as part of cleanup.

### 5. Reconcile manual SQLMesh/Soda asset-check inventory

**Classification:** consolidate after bounded correctness inspection.
**Confidence:** significant finding; implementation choice not yet ratified.

Evidence:

- `packages/databox/databox/orchestration/domains/analytics.py` manually lists
  nine environmental-observations models and four birding-agent models.
- Current CDM/SQLMesh artifacts include additional modeled tables such as
  `dim_bird_species_traits`, `fact_bird_occurrence`,
  `fact_bird_sound_recording`, and `birding_agent.arizona_species_catalog`.
- The same module uses those lists to construct Dagster asset keys and Soda
  checks, while SQLMesh models, `.schema/.../CDM.dbml`, and Soda contract files
  are already separate inventories.
- This is duplicate authority and visible drift risk. It may mean newer models
  lack expected Dagster Soda checks, but this audit did not load Definitions or
  execute checks, so runtime impact is not claimed as proven.

Recommended slice: first inspect exact resolved SQLMesh assets and Soda contract
coverage in a bounded executable ticket, then derive or code-generate the
analytics inventory from one existing authority if current gaps are confirmed.
Do not silently add/remove asset keys under a generic cleanup ticket.

Preservation checks: exact before/after resolved asset keys, jobs and schedules;
one Soda check per governed model; Dagster definitions; contract structure;
SQLMesh lint/tests; generated dictionary coherence.

### 6. Correct small stale ownership descriptions

**Classification:** clarify, bundled only with the owning slice.
**Confidence:** high.

Evidence:

- `packages/databox/databox/config/sources.py` says `settings.sqlmesh_config()`
  catalog dictionaries derive from `SOURCES`; current settings expose one
  `databox` DuckDB catalog and source-specific raw schemas are derived elsewhere.
- The same docstring names the dead standalone `scripts/smoke.py`.
- `packages/databox/pyproject.toml` describes a generic “quality engine” that
  was deliberately deleted; current `databox.quality` contains schema gate and
  code generators.

Repair these descriptions only alongside smoke-runner deletion/package-boundary
cleanup rather than opening a prose-only sweep.

## Keep / rejected cleanup

The following apparent complexity is active or historically authoritative and
must not be removed in this first wave:

- **Rufous large modules and compatibility migrations:** explicitly outside the
  ratified scope. Wishlist removal and legacy personal-collection migration code
  retain active tested lifecycle responsibilities.
- **`scripts/remove_wishlist_storage.py`:** not publicly referenced, but active
  decisions/specifications require an explicit idempotent migration; absence
  from docs is not proof that migration authority may be deleted.
- **`scripts/setup_db_roles.sql` and SQLMesh grants:** the script has no public
  invocation, but model grants actively reference its roles. Clarify or wire it
  only after a separate operational decision; deletion could break grants.
- **Staging/schema/platform-health generators and thin scripts:** each has an
  active Task/CI/test/doc consumer. Thin wrappers are intentional CLI boundaries,
  not duplication.
- **`docs/source-layout.md` and `docs/new-source.md`:** overlap is purposeful:
  the former owns the contract, the latter the operator walkthrough. Cross-link
  and trim contradictions; do not merge by default.
- **Superseded ADRs and `.10x` terminal records:** retained history, not active
  runtime duplication.
- **Generated `docs/dictionary/`:** explicitly generated, published, and drift
  checked; do not hand-edit or remove.
- **`.pi/skills/` and `.schema/`:** core public differentiation and executable
  modeling authority.
- **Two-package workspace:** useful boundary; only the reverse dependency edge
  is unsupported. A package merge would widen scope and churn imports.
- **Taskfile wrappers:** the file intentionally contains only composition,
  environment injection, or non-obvious defaults. No duplicate wrapper set was
  found.

## Recommended child sequence

1. **Repository runtime hygiene** — untrack/ignore Task and agent/runtime noise.
   Independent and lowest risk.
2. **Public warehouse onboarding** — correct README/docs home, split Rufous-only
   operations from warehouse commands/runbook, group nav. Independent of code.
3. **Package dependency direction** — remove the unsupported reverse dependency
   and refresh metadata/lockfile. Independent after baseline.
4. **Delete obsolete smoke runner** — remove only the unreferenced duplicate and
   stale registry prose. Independent of package cleanup.
5. **Reconcile analytics asset/check inventory** — correctness-sensitive and
   dependent on separate exact resolved-inventory evidence.
6. **Aggregate preservation verification** — full Python/source/SQLMesh/Soda/
   docs/static gates plus independent data-engineer navigation and architecture
   reviews.

Slices 1–4 are mechanically bounded and can be implemented separately. Slice 5
must not begin until its exact asset/check semantics are inspected and recorded.

## Limits

- No command loaded Dagster/SQLMesh or imported project modules, so resolved
  runtime asset/check counts were not observed.
- No tests/builds/generators ran; all conclusions are static reference/import and
  tracked-file observations.
- Git history shows intent but does not prove external consumers never invoke an
  unreferenced script. Deletion candidates therefore still require normal
  behavior-preservation tests and review.
- Provider behavior, warehouse contents, performance, and Rufous internals were
  intentionally not audited.
