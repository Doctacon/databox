Status: active
Created: 2026-07-10
Updated: 2026-07-10

# Turbo-search engineering-research skill

## Purpose and scope

This specification governs the canonical Databox skill that teaches Pi agents when and how to use `turbo-search` for self-education and engineering research. It covers cited retrieval, public-site indexing, incremental non-deleting updates, live applies, credential handling, and the boundary between engineering artifacts and externally consumed content.

The governing operating choice is `.10x/decisions/autonomous-turbo-search-engineering-research.md`.

## Artifact contract

- The canonical skill MUST live at `.10x/skills/turbo-search-engineering-research/SKILL.md`.
- A copy-identical exposure MUST live at `.pi/skills/turbo-search-engineering-research/SKILL.md` so trusted Pi sessions discover it automatically.
- The skill name MUST be `turbo-search-engineering-research` to avoid collision with the globally installed `turbo-search-retrieve` skill.
- The frontmatter description MUST begin with `Use when` and specifically trigger for engineering questions that may be answered by indexed websites, repositories, or documentation, and for creating or updating those research indexes.
- The skill MUST be self-contained. It MAY include relative reference files if they materially reduce the main skill's size or maintain a namespace/source inventory.

## Intended use

Turbo-search MUST be framed as a way for the agent to educate itself before reasoning, shaping, planning, ticketing, or implementing engineering work.

The agent MAY use retrieved evidence in:

- its reasoning,
- cited `.10x/research/` findings,
- specifications and decisions,
- plans and tickets,
- implementation guidance and source-backed technical conclusions,
- evidence and reviews that need to identify the inspected source.

The agent MUST NOT use turbo-search as a source for:

- product or application content,
- customer-facing or public-facing prose,
- marketing material,
- runtime-generated responses or dossiers,
- browser/API payload content,
- bulk derivative content corpora,
- bird profiles or any other content prohibited by an active product specification.

Retrieved source text MUST remain bounded and cited in engineering records. Retrieval or indexing MUST NOT be represented as permission to republish, adapt, or operationalize source content.

## Retrieval behavior

- The skill MUST prefer the globally installed `turbo-search` command and document a safe repository fallback when the command is unavailable.
- Questions depending on indexed technical material MUST retrieve evidence before the agent answers from memory.
- Live retrieval MAY run autonomously against a clearly identified namespace.
- Retrieval answers MUST cite the returned page URL or repository path and SHOULD include the page title or section when useful.
- Weak results SHOULD trigger one to three narrower retrieval queries before concluding that the index lacks the answer.
- If the namespace is ambiguous and cannot be derived deterministically from a known source, the agent MUST ask rather than query an invented namespace.

## Index and update behavior

For a public website relevant to a named engineering question or executable ticket, the skill MAY autonomously:

1. crawl or plan locally,
2. inspect generated pages, manifest, chunk output, source scope, and counts,
3. run apply preflight without live calls,
4. create a namespace or apply non-deleting upserts live,
5. retrieve from the resulting namespace and record bounded evidence.

Every live apply MUST:

- have a preceding current plan,
- have a successful non-live apply preflight,
- target the namespace shown by the inspected plan,
- contain no more than 3,000 planned pages and 120,000 planned chunks,
- report exact planned pages/chunks, rows to upsert, embeddings to generate, and stale-row count before execution,
- use upsert-only behavior,
- leave stale rows intact,
- validate the resulting namespace with cited retrieval or the appropriate bounded smoke evaluation,
- record evidence without credentials or sensitive identifiers when the operation supports durable work.

A plan exceeding 3,000 pages or 120,000 chunks MUST NOT be applied under this skill. It MUST return to shaping for an explicit new scope decision.

## Absolute deletion prohibition

The skill MUST prohibit:

- `turbo-search delete-namespace`,
- `turbo-search apply --delete-stale`,
- whole-namespace replacement that removes existing rows,
- direct turbopuffer row deletion,
- any equivalent deletion path, even when deletion appears to be cleanup.

An incremental update MUST retain stale rows. A later request to delete requires superseding the active decision and specification before execution.

## Source, credential, and safety constraints

- Index only sources relevant to a named engineering question or executable ticket; speculative corpus building is excluded.
- Obey robots.txt and default to same-site crawling, conservative concurrency, and crawl delay.
- Do not bypass authentication, paywalls, robots restrictions, anti-bot controls, or source protections.
- Use public source URLs and preserve canonical citation metadata.
- Never print, persist, request in chat, or record `TURBOPUFFER_API_KEY` or other secret values.
- If credentials are unavailable, stop before the live operation and report the missing environment prerequisite without asking the user to paste a key.
- Do not write generated crawl/plan/state artifacts into tracked Databox paths. Use the turbo-search repository's ignored artifact/state locations or a verified temporary location.
- Do not expose turbopuffer configuration or credentials to browser code, API responses, traces, or committed project files.

## Acceptance scenarios

### Indexed engineering question

Given a technical question covered by a known namespace, when the skill runs, then the agent retrieves relevant chunks before answering and cites the returned source URLs or repository paths.

### Missing research index

Given a relevant public technical website without a namespace, when the agent needs it for a named research question, then it may plan, preflight, and live-apply an upsert-only namespace autonomously when the plan is at most 3,000 pages and 120,000 chunks, then validate retrieval.

### Incremental update

Given an existing namespace with changed and stale source chunks, when the skill updates it, then changed/new chunks may be upserted and stale rows remain untouched; no deletion flag or direct delete operation runs.

### Oversized plan

Given a plan above 3,000 pages or 120,000 chunks, when preflight completes, then the live apply does not run and the work returns to shaping for explicit authorization of a different bound or narrower source scope.

### Product-content request

Given a request to use indexed material for a bird profile, product payload, customer-facing copy, marketing material, or runtime-generated dossier, when the skill is considered, then it refuses turbo-search as that content source and follows the governing product specification instead.

### Protected source

Given a source requiring authentication, paywall bypass, robots evasion, or anti-bot circumvention, when indexing is considered, then the skill does not crawl or apply it.

### Missing credentials

Given a valid bounded live plan but no API key in the environment, when apply is considered, then the agent reports the missing prerequisite without exposing or soliciting the secret and performs no live call.

### Deletion request

Given a request to delete a namespace or stale rows, when the skill runs, then it identifies the active prohibition and performs no deletion.

## Explicit exclusions

- No product-content generation, runtime retrieval feature, browser integration, API endpoint, or customer-facing RAG behavior.
- No namespace or row deletion.
- No authenticated/private-source indexing or protection bypass.
- No new custom Pi extension or typed turbo-search tool in the first implementation; the existing `bash` capability and CLI are sufficient.
- No prompt template or Pi package in the first implementation.
