Status: active
Created: 2026-07-10
Updated: 2026-07-10

# Allow autonomous non-deleting turbo-search operations for engineering research

## Context

Databox agents need a repository-local policy for using the installed `turbo-search` CLI and turbopuffer namespaces. The globally available `turbo-search-retrieve` skill supports cited retrieval, while the global `turbopuffer-site-rag` skill requires fresh user approval before every live write. Neither artifact expresses Databox's intended boundary: turbo-search is an agent-education and engineering-research capability, not a source for product or customer-facing content.

The CLI can perform local crawl/plan/preflight work, live retrieval, live namespace upserts, stale-row deletion, and whole-namespace deletion. Live indexing incurs embedding and turbopuffer cost. Current planning caps permit up to 3,000 pages and 120,000 chunks.

The user ratified the operating boundary in the 2026-07-10 workstream: engineering artifacts are permitted outputs; live indexing, updating, and applying may be autonomous up to the CLI caps; all deletion is prohibited.

## Decision

1. Databox will expose a repository-local Pi skill whose canonical source lives under `.10x/skills/` and whose Pi exposure is a copy-identical mirror under `.pi/skills/`.
2. Turbo-search MUST be used to educate the agent and support named engineering work. Permitted persisted outputs are bounded, cited research, specifications, plans, tickets, and implementation guidance.
3. Turbo-search MUST NOT be used to generate or supply product content, customer-facing content, marketing content, runtime-generated content, species dossiers, or another externally consumed content corpus.
4. Retrieval does not grant content-reuse rights. Source licensing, attribution, freshness, and product-data approval remain separate requirements.
5. The agent MAY autonomously perform local crawl, plan, and apply-preflight operations; live retrieval; and live namespace creation or non-deleting upserts when relevant to a named engineering question or executable ticket.
6. Autonomous live applies are authorized up to the current turbo-search planning caps of 3,000 pages and 120,000 chunks. A plan above either cap is not authorized by this decision and requires a new explicit scope decision.
7. The agent MUST run and inspect the local plan and non-live apply preflight before every live apply. It MUST verify the intended namespace, page/chunk counts, upsert counts, stale-row count, source scope, and generated artifacts before proceeding.
8. The agent MUST NOT delete a namespace, delete stale rows, replace a namespace destructively, or invoke any equivalent deletion path. Updates are upsert-only and retain stale remote rows.
9. Public-source indexing MUST remain same-site and robots-compliant by default, use conservative crawl behavior, and MUST NOT bypass authentication, paywalls, robots controls, or anti-bot protections.
10. Credentials MUST remain in environment or shell memory and MUST NOT appear in prompts, logs, project records, generated artifacts, or committed files.
11. For Databox work, this decision supersedes the global `turbopuffer-site-rag` skill's per-live-apply approval requirement only for the bounded, non-deleting operations above. All stricter credential, crawl-ethics, plan/preflight, citation, and evidence guardrails remain in force.
12. Existing active product specifications that exclude turbo-search content remain authoritative. In particular, `.10x/specs/arizona-bird-catalog-and-profile.md` and `.10x/specs/avonet-bird-traits-source.md` continue to prohibit a turbo-search bird corpus or runtime narrative-profile source.

## Alternatives considered

- **Retrieval only:** rejected because Databox agents should be able to create and maintain useful engineering-research indexes.
- **Fresh confirmation before every live apply:** rejected by the user in favor of autonomous bounded operation.
- **A smaller autonomous limit of 500 pages and 20,000 chunks:** rejected by the user; the current CLI maximums are authorized.
- **Allow stale-row cleanup while forbidding whole-namespace deletion:** rejected; all deletion is prohibited.
- **Allow product or customer-facing content with approval:** rejected; the selected boundary is engineering artifacts only.
- **Use only the global skill:** rejected because its approval policy conflicts with the ratified Databox-local operating model and it is not repository-portable.

## Consequences

- Agents can incur live embedding and turbopuffer cost without a fresh prompt, up to the explicit 3,000-page and 120,000-chunk bounds.
- Plan and preflight inspection become mandatory evidence gates rather than approval gates.
- Remote namespaces may accumulate stale rows because deletion is prohibited; future cleanup requires an explicit superseding decision.
- The repository skill must clearly distinguish learning that informs engineering work from externally consumed content generation.
- A uniquely named repository skill is preferable to colliding with the globally installed `turbo-search-retrieve` skill, because Pi keeps only the first discovered skill on a name collision.
