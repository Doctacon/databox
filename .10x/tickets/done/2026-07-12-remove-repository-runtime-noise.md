Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md
Depends-On: .10x/tickets/done/2026-07-12-audit-warehouse-repository-simplicity.md

# Remove repository runtime noise

## Scope

Remove tracked Task runtime checksums and prevent local runtime artifacts from
appearing as repository changes.

- untrack `.task/checksum/*`;
- ignore `.task/`, `.pi-subagents/`, and `.deepeval/`;
- preserve tracked `.pi/skills/`, `.schema/`, `.10x/`, and generated dictionary
  authorities.

## Acceptance criteria

- No `.task/checksum/*` path remains tracked.
- Task, subagent, and DeepEval runtime paths are ignored.
- No authority/source artifact is ignored or removed accidentally.
- Ignore behavior has direct assertions using `git check-ignore`.
- Existing repository hygiene/static checks pass.

## Explicit exclusions

- Deleting tracked Pi skills, schema/CDM artifacts, durable records, or docs
- Changing Task behavior or commands
- Removing unrelated local developer files

## Evidence expectations

Record tracked paths removed, ignore assertions, preserved-authority checks, and
validation results.

## Progress and notes

- 2026-07-12: Opened from the high-confidence runtime-noise finding in the
  warehouse simplicity audit.
- 2026-07-12: Deleted the only three tracked Task checksum cache files and added exact `.task/`, `.pi-subagents/`, and `.deepeval/` ignore rules. Repository-native assertions confirm all three runtime roots are ignored while `.pi/skills`, `.schema`, `.10x`, and `docs/dictionary` have zero ignored tracked paths. No existing hygiene-test surface warranted a new test. `git diff --check` and empty staging passed. Evidence: `.10x/evidence/2026-07-12-repository-runtime-noise-removal.md`.
- 2026-07-12: Independent review `.10x/reviews/2026-07-12-repository-runtime-noise-removal-review.md` passed every criterion. Retrospective: mutable tool runtime belongs in ignore rules, while tracked skills/schema/records remain explicit authorities. Ticket closed.

## Blockers

None.
