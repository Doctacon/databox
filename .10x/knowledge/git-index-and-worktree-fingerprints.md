Status: active
Created: 2026-09-12
Updated: 2026-09-12

# Git and worktree preservation fingerprints

## Distinguish the invariants

A raw `.git/index` digest measures the entire index file, not just what is staged. A logical index inventory measures path, stage, mode and blob OID. File-content/permission fingerprints measure the working tree separately. None substitutes for the others.

Git can refresh index metadata without staging changes. That possibility is not attribution: an unexplained byte difference must not be called a benign cache refresh without supporting evidence. Use `--no-optional-locks`/`GIT_OPTIONAL_LOCKS=0` for observational Git commands, but do not claim this prevents another process or harness from updating the index.

For new preservation checks, retain a bounded logical entry inventory alongside the raw digest and relevant timestamps. Record observation boundaries precisely. A baseline's HEAD plus empty-staged assertion supports comparison to that HEAD, but does not reconstruct old raw index bytes or all old internal flags. Do not reset/recreate an index merely to make a raw-digest assertion pass.

## Symlinks and inventory limits

Git records a symlink's link-text blob and type mode (`120000`), not its filesystem permission bits. Compare committed link content/type separately from filesystem permission fingerprints; treating them as the same representation creates a false mismatch. This does not waive either applicable check.

Unrelated preexisting symlinks can be protected by fingerprinting their file type and link-text bytes without following or exporting their targets. They are not regular files to open with `O_NOFOLLOW`, nor authority to copy target contents. This distinction does not relax strict no-follow checks for selected source payloads or destination components.

A tracked/nonignored inventory does not prove historical byte-preservation of ignored private files. State that limit rather than sweeping credentials, caches, state or unrelated data into a preservation bundle. Later authorized record maintenance must be distinguished from the worktree state at the original verification timestamp.

## Provenance and limits

These lessons arose from `.10x/evidence/2026-09-11-private-recovery-originals.md` and `.10x/reviews/2026-09-12-private-recovery-originals-review.md`: the copies/protected work and current logical index verified, but raw index bytes differed later and the writer remained unknown. The reviewer retained concerns; the parent accepted that bounded attribution limit without repairing the index or claiming an unchanged raw index through review time.
