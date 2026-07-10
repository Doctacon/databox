Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Target: .10x/skills/turbo-search-engineering-research/SKILL.md, .pi/skills/turbo-search-engineering-research/SKILL.md, .10x/tickets/done/2026-07-10-create-turbo-search-engineering-research-skill.md
Verdict: pass

# Turbo-search engineering-research skill review

## Target

The canonical repository skill, its Pi exposure, and the implementation ticket governed by `.10x/specs/turbo-search-engineering-research-skill.md` and `.10x/decisions/autonomous-turbo-search-engineering-research.md`.

## Findings

### Resolved during review

- **Significant:** The first implementation prohibited recording any turbopuffer “configuration,” which conflicted with required engineering evidence such as namespace and source identity. The final skill protects credentials and sensitive/private configuration while explicitly allowing bounded non-secret namespace, public source, region/model, and count metadata in cited engineering records.
- **Minor:** The first plan example required conservative concurrency and delay without setting explicit values. The final example uses global concurrency `2`, per-domain concurrency `2`, and a `0.5`-second delay, with stricter site requirements, robots directives, and source terms taking precedence.
- **Significant evidence gap:** Initial review found no direct Pi discovery output. `.10x/evidence/2026-07-10-turbo-search-engineering-research-skill.md` now records a one-shot offline/no-session Pi startup that discovered the skill without a collision warning or persistent trust mutation.

### Final acceptance assessment

All twelve ticket acceptance criteria are supported:

- valid canonical skill frontmatter and exact unique name,
- byte-identical canonical and `.pi` exposure files,
- direct Pi discovery without a same-name collision,
- agent-education and cited-engineering-artifact framing,
- explicit prohibition of product, customer/public-facing, marketing, runtime/dossier, browser/API, bird-profile, and bulk derivative content,
- autonomous local planning/preflight, live retrieval, namespace creation, and non-deleting upserts for named engineering work,
- mandatory inspected plan and non-live preflight with 3,000-page and 120,000-chunk limits,
- prohibition of namespace deletion, stale-row deletion, destructive replacement, direct row deletion, and equivalent cleanup paths,
- robots, same-site, crawl-delay, credential, citation, source-protection, and content-rights guardrails,
- correct installed CLI and fallback guidance,
- generated-artifact exclusion from tracked Databox paths,
- recorded static and direct discovery validation.

No live turbo-search operation was run during implementation or review.

## Verdict

**Pass.** No blocker or fix-worth-doing-now remains within the approved ticket.

The final reviewer response itself returned a pass. The subagent harness marked that run failed only because its structured acceptance wrapper expected a `tests-added` field; the reviewer explicitly found that no tests were appropriate for this operational-skill change and accepted the direct discovery and static validation instead. The parent independently inspected the files and raw evidence before recording this review.

## Residual risk

- Future Pi or turbo-search versions may change skill discovery or CLI flags; the skill must be revalidated when those surfaces change.
- Static instructions and discovery cannot prove every future agent will comply.
- The worktree contained unrelated pre-existing changes; review and evidence were scoped to ticket-owned paths.
