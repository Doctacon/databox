Status: done
Created: 2026-08-31
Updated: 2026-08-31
Parent: None
Depends-On: None

# Organize root tests and scripts by domain

## Cold-start context

The repository root currently has 64 Python test modules directly under `tests/` and 38 operational files directly under `scripts/`. The user confirmed that these two flat root directories are unwieldy and authorized a domain-based reorganization with a clean path break. Package-local test suites are already organized and are outside this ticket.

This is a behavior-preserving repository-layout change. Existing commands, test discovery, imports, generated-resource lookup, documentation, CI, Task targets, static contract assertions, and operational behavior must continue to work through the new canonical paths. No compatibility wrappers should remain at old script paths.

## Ratified organization

Use these domain directories, retaining a directory only when at least one owned file belongs there:

- `platform/` — bootstrap, settings, metrics, secrets, schema/dev verification, repository-level documentation/navigation checks, and common developer tooling.
- `sources/` — source registry, source builders, source layout/modeling contracts, source CI, source ingestion/refresh, Quack destinations, and source-specific model/orchestration tests.
- `analytics/` — analytics contracts, SQLMesh/model tests, staging generation, exports, audits, platform-health generation, and production SQL planning.
- `birding/` — catalog, trip planning, alerts, personal collection, target/watch behavior, maps/places/weather, recommendation media, privacy remediation, and local birding runtime.
- `rufous_media/` — Rufous public/media ingest, selection, preparation, review, approval, pinning, hydration, publication, release, and associated audits.
- `cloudflare/` — Cloudflare Workers AI tests and smoke tooling.
- `operations/` — shared shell/SQL operational commands that do not have a clearer domain owner, including logging, pre-commit setup, and database-role setup.
- `evals/` — retain the existing evaluation grouping.
- `templates/` — retain script templates alongside the script that consumes them, with resource lookup repaired as needed.

When a file could fit multiple domains, place it with the product or workflow it primarily verifies or operates. Prefer the smallest understandable taxonomy; do not add deeper technical-type subfolders unless required to avoid a still-unwieldy domain.

## Scope

- Move every directly nested regular file in root `tests/` into the ratified domain folders, except existing intentionally nested content such as `tests/evals/`, which remains grouped.
- Move every directly nested regular file in root `scripts/` into the ratified domain folders.
- Keep `scripts/templates/` organized and repair template lookup after its owning generator moves.
- Update all active references to moved paths, including:
  - Python imports and filesystem constants;
  - `Taskfile.yaml`;
  - `.github` workflows and repository automation;
  - `pyproject.toml`, hooks, scaffold/configuration files, and shell scripts;
  - active documentation and README files;
  - tests and source-code string contracts that intentionally validate commands;
  - current `.10x` active authority only where it asserts a now-current path.
- Preserve pytest collection, coverage, MyPy/Ruff behavior, script execution from repository root, and resource lookup.
- Remove incidental tracked or untracked `__pycache__` artifacts under the reorganized directories if present; do not commit runtime artifacts.

## Explicit exclusions

- Do not reorganize `packages/databox-sources/tests/`, tests colocated elsewhere, app/frontend tests, or other repository directories.
- Do not change product behavior, command semantics, data contracts, source registry semantics, release policy, or operational side effects.
- Do not rename script basenames or test basenames unless a collision in one destination makes it mechanically necessary.
- Do not add old-path compatibility wrappers, symlinks, or duplicate entry points.
- Do not rewrite terminal `.10x` records merely because they truthfully cite historical paths.
- Do not perform unrelated cleanup or refactoring.

## Acceptance criteria

1. No regular test module remains directly under root `tests/`; the existing `evals/` suite and all moved tests are discoverable recursively by the existing test tooling.
2. No regular script remains directly under root `scripts/`; every script is located in one ratified domain folder, while templates remain coherently owned.
3. All active repository references resolve to the new canonical paths; an exact reference scan finds no stale old script/test path outside truthful terminal history or intentionally documented migration history.
4. `Taskfile.yaml`, CI, hooks, docs, scaffold behavior, static command contracts, and Python resource lookup use the new paths.
5. The complete default Python test suite passes with unchanged network-safety expectations.
6. Relevant Ruff, format-check, MyPy, documentation, secret, source-layout/modeling, and repository diff checks pass.
7. No compatibility wrapper, duplicate script implementation, committed cache, generated runtime output, or unrelated change is introduced.
8. A reviewer confirms the domain allocation is coherent, the move is behavior-preserving, and no operational command or test suite was silently orphaned.

## Evidence expectations

Record:

- before/after inventories for direct files and domain folders;
- a move map for all root test and script files;
- stale-reference scans with exclusions and limits stated;
- pytest collection and complete default-suite results;
- focused results for path-sensitive tests, Task targets, generators in check mode, command-contract tests, docs, static typing/lint/format, and secret checks;
- `git diff --check`, final status, and confirmation that no cache/generated runtime artifact is included;
- limits for commands not executed because they would mutate production data or call live providers.

## Blockers

None. The default-suite fixture drift and USFWS source-contract mismatch discovered during verification were repaired under separate done tickets.

## References

- `.10x/knowledge/warehouse-first-cleanup.md`
- `.10x/research/2026-07-12-warehouse-repository-simplicity-audit.md`
- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/specs/registry-derived-source-verification.md`
- `Taskfile.yaml`
- `pyproject.toml`
- `.github/`
- `docs/`

## Progress and notes

- 2026-08-31: Inspected root layout, active/terminal 10x records, direct `tests/` and `scripts/` inventories, and current path references. No active ticket already owned this reorganization.
- 2026-08-31: User ratified root `tests/` plus root `scripts/`, domain-based grouping, the listed taxonomy, and a clean path break with all consumers updated atomically.
- 2026-08-31: Moved all 70 directly nested root test modules, 39 directly nested root script files, and five owned templates into the ratified domain directories. Updated Taskfile, workflows, hooks, scaffold, docs, runtime filesystem seams, imports, and static command/path contracts. Added `tests/platform/test_repository_layout.py` to prevent regression.
- 2026-08-31: Structural verification reports 114/114 new paths present, zero old paths present, zero direct root files, and no stale active old-path reference outside one explicit pre-change historical citation and four intentional retired-authority guards.
- 2026-08-31: Focused path-sensitive suite passed 198/198. Ruff, format, MyPy (140 files), source-modeling (8 sources), staging/platform-health/dictionary drift, strict MkDocs, secret scan (1,047 files), and diff checks passed. Evidence: `.10x/evidence/2026-08-31-root-test-script-domain-reorganization.md`.
- 2026-08-31: Complete network-blocked Python suite completed at 1,491 passed, 3 failed, 7 snapshots passed, and 84.89% coverage. All three failures reproduce focused in pure-renamed tests and are recorded separately at `.10x/tickets/done/2026-08-31-repair-preexisting-default-python-test-failures.md`; they were not patched under this layout ticket.
- 2026-08-31: The moved source-layout checker and the pre-change checker both fail identically on the registered explicit-target-only USFWS domain, and source-CI matrix validation inherits that baseline failure. Opened `.10x/tickets/done/2026-08-31-reconcile-usfws-source-contract-checker.md`; no unsafe implicit USFWS job was added.
- 2026-08-31: Implementation is complete but the ticket remains active: acceptance criteria 5 and 6 lack green aggregate gates due to proven pre-existing failures, and criterion 8 awaits independent review.
- 2026-08-31: Independent review found two ticket-scoped defects: the four moved SQLMesh shell scripts resolved only one parent level and therefore treated `scripts/` as the repository root, and `test_metrics.py` contradicted the explicitly ratified `platform/` allocation.
- 2026-08-31: Repaired all four SQLMesh scripts to resolve `../..`; added a non-mutating temporary-repository/fake-executable regression covering every script and expected plan count. Moved `test_metrics.py` from `tests/analytics/` to `tests/platform/` and updated `docs/metrics.md`. Focused verification passed 10/10 tests, Ruff, format, `bash -n`, active-reference scan, and diff check. Evidence was appended at `.10x/evidence/2026-08-31-root-test-script-domain-reorganization.md`.
- 2026-08-31: The separately ticketed three default-suite failures and USFWS source-contract mismatch were deliberately not addressed or rerun in this review repair. Ticket remains open for reviewer re-verification and aggregate closure policy.
- 2026-08-31: Broader safe review-repair verification collected 1,498 tests, passed repository-wide Ruff/format, strict MkDocs, tracked and untracked secret scans, and `git diff --check`. No live or mutating workflow ran.
- 2026-08-31: Independent follow-up review found both in-scope defects resolved and no remaining reorganization defect. Review: `.10x/reviews/2026-08-31-root-test-script-domain-reorganization-follow-up-review.md`. Acceptance criteria 5 and 6 remained literally red due to the separately owned baseline failures, so this ticket remained open rather than claiming unsupported closure.
- 2026-08-31: The three default-suite fixture failures were repaired under `.10x/tickets/done/2026-08-31-repair-preexisting-default-python-test-failures.md`; a complete network-blocked rerun passed 1,498 tests and 7 snapshots at 85.00% coverage.
- 2026-08-31: The USFWS explicit-target-only contract was reconciled under `.10x/tickets/done/2026-08-31-reconcile-usfws-source-contract-checker.md`. Final aggregate verification passed 1,504 network-blocked tests, seven snapshots, 85% coverage, and an 8/8 source checker/matrix with relevant static gates green.
- 2026-08-31: Final independent review passed with every acceptance criterion supported: `.10x/reviews/2026-08-31-root-test-script-domain-reorganization-final-review.md`. Ticket closed.
- 2026-08-31 retrospective: Script moves require explicit repository-root regression tests, while aggregate verification may expose unrelated baseline drift. The repository-layout test, explicit-target contract tests, active specifications, and dedicated evidence preserve these lessons; no additional knowledge or skill record is warranted.
