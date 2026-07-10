Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-10-create-turbo-search-engineering-research-skill.md, .10x/specs/turbo-search-engineering-research-skill.md, .10x/decisions/autonomous-turbo-search-engineering-research.md

# Turbo-search engineering-research skill validation

## What was observed

The repository-local skill was present at both required paths, Pi directly discovered the exposed skill during a one-shot offline startup, no same-name collision warning appeared, and temporary one-run project approval did not modify the persistent trust file.

Observed bounded output:

```text
discovered_skill=True
collision_warning=False
startup_line=pi-subagents, proton-pass-agent, turbo-search-engineering-research,
trust_hash_before=24997c299a3f371913e7b2fc69401aa4e921107c22db78b6c05930a2a1ae499e
trust_hash_after=24997c299a3f371913e7b2fc69401aa4e921107c22db78b6c05930a2a1ae499e
pi_discovery_exit=0
skill_sha256=4a444735851cfa92e1080bebe6b6fc1dfdecf6221935ef22f635e4006fb6eb16
frontmatter_valid=true
global_name_retrieve=turbo-search-retrieve
global_name_site_rag=turbopuffer-site-rag
cli_path=/Users/crlough/.local/bin/turbo-search
plan_flags=--concurrent-requests,--concurrent-requests-per-domain,--download-delay,--max-chunks,--max-pages,
apply_contract=--approve,--delete-stale,safe preflight,upsert only new/changed rows,
retrieve_flags=--live,--namespace,--top-k,
diff_check_exit=0
```

The canonical and `.pi` exposure files compared byte-for-byte equal before the shared SHA-256 was printed.

## Procedure

From the Databox repository root:

1. Hashed `~/.pi/agent/trust.json` without printing its contents.
2. Started Pi through a temporary pseudo-terminal with `PI_OFFLINE=1`, `--no-session`, one-run `--approve`, `--no-extensions`, `--no-prompt-templates`, and `--no-themes`; immediately sent `/quit`.
3. Removed terminal escapes from the temporary output, required `turbo-search-engineering-research` to appear, and failed if a same-name collision warning appeared.
4. Rehashed `trust.json` and required the hash to remain unchanged.
5. Compared `.10x/skills/turbo-search-engineering-research/SKILL.md` and `.pi/skills/turbo-search-engineering-research/SKILL.md` byte-for-byte and recorded the canonical SHA-256.
6. Parsed YAML frontmatter with Ruby safe loading and required the exact name plus a description beginning with `Use when`.
7. Read the distinct names from the two relevant global skills.
8. Inspected bounded `turbo-search plan --help`, `apply --help`, and `retrieve --help` output for the flags and safe preflight/upsert contract used by the skill.
9. Ran `git diff --check` on the two skills and owning ticket.

No live retrieval, crawl, plan, apply, evaluation, namespace, row-deletion, or namespace-deletion operation ran. No model request was submitted. The temporary startup capture was removed after validation.

## What this supports

This evidence supports ticket acceptance criteria 1-3, 7-10, and 12 directly:

- valid canonical skill identity and exposure,
- byte-identical canonical/exposed files,
- direct Pi project-skill discovery without a same-name collision warning,
- installed CLI availability and command-surface compatibility,
- plan/preflight/apply and deletion-flag accuracy,
- no persistent trust mutation,
- clean ticket-owned diff formatting.

Inspection of the recorded skill text supports criteria 4-6 and 8-11; the independent review record evaluates those semantic criteria.

## Limits

- This validates discovery and static operational instructions, not a live turbopuffer request or write.
- It does not prove future versions of Pi or turbo-search retain the same discovery or CLI behavior.
- It does not prove every future agent will follow the skill correctly.
- The repository contained unrelated pre-existing changes; this procedure inspected only ticket-owned paths and did not attribute or validate unrelated work.
