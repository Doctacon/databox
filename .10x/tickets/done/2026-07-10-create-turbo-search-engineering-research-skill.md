Status: done
Created: 2026-07-10
Updated: 2026-07-10
Parent: None
Depends-On: None

# Create the repository-local turbo-search engineering-research skill

## Scope

Create one canonical 10x operational skill and its copy-identical Pi exposure so Databox agents use `turbo-search` for self-education and engineering research, can autonomously retrieve/index/update/apply within ratified bounds, and cannot use it for external content generation or deletion.

Before authoring, the executor MUST verify whether an active skill-writing skill exists under `.10x/skills/` and follow it if present. The 2026-07-10 shaping inspection found domain workflow skills but no skill-writing governor.

## Governing records

- `.10x/decisions/autonomous-turbo-search-engineering-research.md`
- `.10x/specs/turbo-search-engineering-research-skill.md`
- `.10x/research/2026-07-09-local-birding-pokedex-watch-architecture.md`
- `.10x/decisions/local-single-user-birding-pokedex-expansion.md`
- `.10x/specs/arizona-bird-catalog-and-profile.md`
- `.10x/specs/avonet-bird-traits-source.md`
- Global reference skill: `/Users/crlough/.pi/agent/skills/turbo-search-retrieve/SKILL.md`
- Global operational reference: `/Users/crlough/.pi/agent/skills/turbopuffer-site-rag/SKILL.md`

## Acceptance criteria

1. `.10x/skills/turbo-search-engineering-research/SKILL.md` exists with valid required 10x frontmatter, including the exact skill name and a specific `Use when...` description.
2. `.pi/skills/turbo-search-engineering-research/SKILL.md` exists and is byte-for-byte identical to the canonical source.
3. Pi discovery does not introduce a skill-name collision with the globally installed `turbo-search-retrieve` or `turbopuffer-site-rag` skills.
4. The skill clearly states that turbo-search educates the agent and may inform cited engineering research, decisions, specs, plans, tickets, reviews, evidence, and implementation guidance.
5. The skill clearly prohibits product, customer-facing, marketing, runtime-generated, dossier, browser/API, and bulk derivative content use.
6. The skill permits autonomous local crawl/plan/preflight, live retrieval, namespace creation, and non-deleting live upserts for named engineering work.
7. The skill requires plan and non-live preflight inspection before every live apply and enforces the ratified maximum of 3,000 pages and 120,000 chunks.
8. The skill prohibits whole-namespace deletion, stale-row deletion, destructive replacement, direct row deletion, `delete-namespace`, and `--delete-stale`.
9. The skill preserves robots/same-site/crawl-delay, credential secrecy, citation, source-protection, and no-content-reuse guardrails.
10. The skill explains the globally installed CLI check and fallback without embedding credentials or requiring project code changes.
11. The skill prevents generated crawl/plan/state artifacts from entering tracked Databox paths.
12. Validation demonstrates valid frontmatter, canonical/exposure equality, CLI availability or documented fallback, and expected Pi skill discovery after project trust/reload.

## Evidence expectations

- Paths and byte-equality check for canonical and exposed `SKILL.md` files.
- Frontmatter validation showing the exact name, activation description, and metadata dates.
- `command -v turbo-search` and bounded help output demonstrating the expected CLI surface without secrets.
- Pi startup/reload or equivalent discovery evidence showing `turbo-search-engineering-research` is available without a name-collision warning.
- Targeted review mapping the content-generation boundary, autonomous write bounds, mandatory plan/preflight, absolute deletion prohibition, and credential/crawl safeguards to the active specification.

## Explicit exclusions

- No Pi extension, custom typed tool, prompt template, package publication, product/runtime integration, namespace operation, live retrieval, or live apply as part of implementing this skill.
- No changes to the globally installed skills.
- No changes to active birding product behavior or source/model specifications.
- No generated crawl or plan artifacts.

## Assumption provenance

- **User-ratified:** canonical `.10x/skills/` source and `.pi/skills/` exposure; engineering-artifact-only use; autonomous live indexing/updating/applying; 3,000-page and 120,000-chunk autonomous limits; prohibition of all namespace and stale-row deletion.
- **Record-backed:** CLI plan/preflight/apply mechanics, retrieval citation fields, safe credential handling, robots/same-site defaults, and current Pi skill discovery/collision behavior.
- **Blocked:** None.

## Progress and notes

- 2026-07-10: Shaping confirmed the repository-local canonical/exposure pattern. Existing Databox skills use copy-identical `.10x/skills/` and `.pi/skills/` files.
- 2026-07-10: User selected autonomous live writes, engineering artifacts as the only persisted output category, CLI maximum planning caps, and prohibition of both namespace and stale-row deletion.
- 2026-07-10: User authorized execution; ticket moved to active for delegated implementation.
- 2026-07-10: Implemented canonical `.10x/skills/turbo-search-engineering-research/SKILL.md` and copy-identical `.pi/skills/turbo-search-engineering-research/SKILL.md`. The skill frames turbo-search as agent education for cited engineering artifacts, permits autonomous plan/preflight/retrieval/non-deleting apply within 3,000-page/120,000-chunk bounds, and prohibits product/runtime content generation plus every deletion path.
- 2026-07-10: Validation passed for byte equality (SHA-256 `9be27a9ed4dc0b2bd2bc5aea5c08e79ac7fb60fc80394c41b0a8d598ae2f70cc`), required frontmatter, unique project skill name, policy assertions, documented Pi `.pi/skills/**/SKILL.md` discovery behavior, CLI/help surface, whitespace, and no staged files. The first Ruby YAML check rejected date scalars because `Date` was not permitted; the corrected safe-load check explicitly permitted `Date` and passed. No live turbo-search operation ran.
- 2026-07-10: Applied accepted review fixes: non-secret namespace/source/region/model/count metadata is now explicitly recordable while credentials and sensitive/private configuration remain prohibited; the plan example now uses concurrency `2` per global/domain and `0.5`-second delay with stricter site requirements taking precedence. A one-shot offline/no-session Pi startup with temporary `--approve` and `/quit` directly discovered `turbo-search-engineering-research` without a collision warning or model call. Canonical and Pi exposure remain byte-identical at SHA-256 `4a444735851cfa92e1080bebe6b6fc1dfdecf6221935ef22f635e4006fb6eb16`; frontmatter, unique names, CLI help, diff check, and no-staged-files checks passed. No live turbo-search operation ran.
- 2026-07-10: Recorded reproducible raw validation in `.10x/evidence/2026-07-10-turbo-search-engineering-research-skill.md`. Final independent review passed in `.10x/reviews/2026-07-10-turbo-search-engineering-research-skill-review.md`; no blocker or fix-worth-doing-now remains.
- 2026-07-10: Retrospective completed. The durable operational learning is the skill itself: separate agent education/engineering artifacts from externally consumed content, require plan plus preflight before bounded autonomous upserts, and prohibit every remote deletion path. The one-shot offline Pi discovery procedure is preserved in evidence; no additional knowledge record, skill, or follow-up ticket is warranted.

## Closure evidence

- Criteria 1-3 and 12: `.10x/evidence/2026-07-10-turbo-search-engineering-research-skill.md` records valid frontmatter, byte equality, distinct global names, direct Pi discovery, no collision warning, unchanged persistent trust hash, and clean diff validation.
- Criteria 4-11: `.10x/reviews/2026-07-10-turbo-search-engineering-research-skill-review.md` maps the final skill to the engineering-content boundary, bounded autonomous operations, mandatory plan/preflight, deletion prohibition, credential/crawl/citation safeguards, CLI fallback, and tracked-artifact exclusion.
- Canonical implementation: `.10x/skills/turbo-search-engineering-research/SKILL.md`.
- Pi exposure: `.pi/skills/turbo-search-engineering-research/SKILL.md`.
- Residual risk is limited to future Pi/CLI drift and agent compliance; it does not block the current contract.

## Blockers

None.
