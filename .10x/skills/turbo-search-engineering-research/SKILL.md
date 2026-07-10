---
name: turbo-search-engineering-research
description: "Use when an engineering question may be answered by websites, documentation, or repositories indexed by turbo-search, or when a relevant public research index must be created or updated."
metadata:
  created: 2026-07-10
  updated: 2026-07-10
---

# Turbo-search engineering research

## Objective

Use `turbo-search` to educate yourself before reasoning, shaping, planning, ticketing, reviewing, or implementing engineering work.

**Core boundary:** turbo-search is an agent-learning and engineering-research tool. It is not a content-generation source outside the agent.

You may preserve bounded, cited findings in engineering artifacts—research, decisions, specifications, plans, tickets, evidence, reviews, and implementation guidance. Those artifacts record what you learned and why an engineering conclusion follows. Do not turn retrieved material into product content, customer-facing or public-facing prose, marketing copy, runtime-generated responses or dossiers, browser/API payloads, or bulk derivative corpora. Do not use turbo-search for bird profiles or any content prohibited by an active product specification.

Retrieval and indexing do not grant permission to republish, adapt, or operationalize source content. Licensing, attribution, freshness, and product-data approval remain separate requirements.

## Databox authority

For Databox work, this repository skill governs turbo-search use. It supersedes the globally installed `turbopuffer-site-rag` skill only where that skill requires fresh approval for each bounded live write. Its credential, crawl-ethics, plan/preflight, citation, and evidence protections still apply.

Within this skill's bounds, you may autonomously:

- run local crawl, plan, and apply-preflight operations,
- retrieve live cited context,
- create a research namespace,
- upsert new or changed rows into a research namespace.

Every live apply requires a current inspected plan and a successful non-live preflight. A plan may contain at most **3,000 pages** and **120,000 chunks**. All deletion is prohibited.

## Prerequisites

Prefer the globally installed CLI. Use the local repository fallback only when needed:

```bash
command -v turbo-search
# Fallback repository:
cd /Users/crlough/Code/personal/turbo-search
uv run turbo-search --help
```

Live retrieval and apply require `TURBOPUFFER_API_KEY` in the environment. Check only whether it is set:

```bash
test -n "${TURBOPUFFER_API_KEY:-}" \
  && echo "TURBOPUFFER_API_KEY is set" \
  || echo "TURBOPUFFER_API_KEY is missing"
```

Never print, log, persist, or ask the user to paste a secret. Do not record password-manager output, private vault or item names, tokens, share IDs, or credential values. If the key is unavailable, stop before the live operation and report the missing environment prerequisite.

Use the global CLI for retrieval. Run crawl/plan/apply workflows from `/Users/crlough/Code/personal/turbo-search` so generated artifacts and applied state stay in that repository's ignored locations. Before writing them, verify the selected `artifacts/` and `.turbo-search/` paths are ignored. If the repository is unavailable, use a verified temporary location or ask for the clone path; do not place generated artifacts in tracked Databox paths.

## Decide whether turbo-search applies

Use turbo-search only for a named engineering question or executable ticket.

Use it when:

- current technical documentation or an indexed repository can answer the question,
- source-backed implementation guidance is needed,
- research should support a decision, specification, plan, ticket, evidence item, or review,
- a relevant public technical site needs a bounded research index.

Do not use it when:

- the desired output is product or application content,
- retrieved prose would be shown to customers or emitted at runtime,
- the task would build a dossier or derivative content corpus,
- an active specification excludes that source or content family,
- the source requires authentication, paywall bypass, robots evasion, or anti-bot circumvention,
- the indexing would be speculative rather than tied to named engineering work.

## Retrieve cited context

1. Identify the namespace.
   - Use a namespace supplied by the user or an active record exactly.
   - Derive a deterministic namespace only when the mapping is obvious:
     - website: `site-<host-with-non-alphanumerics-as-hyphens>-v1`
     - GitHub repository: `github-<owner>-<repo>-v1`
   - If the namespace remains ambiguous, ask rather than query an invented namespace.
2. Turn the need into a narrow, standalone engineering question.
3. Run live retrieval:

```bash
turbo-search retrieve "<standalone engineering question>" \
  --live \
  --namespace "<namespace>" \
  --top-k 5 \
  --json
```

4. Treat `title`, `url`, `section_path`, and `content` as the evidence base.
5. If results are weak, run one to three narrower queries before concluding that the index lacks the answer.
6. Answer or record the engineering finding with citations. Cite page URLs for websites and repository paths/URLs for repositories. Keep quotations bounded; synthesize the engineering conclusion rather than reproducing source content.

A successful live retrieval reports `command: retrieve`, `dry_run: false`, `api_calls_occurred: true`, the intended namespace, and relevant hits.

## Create or update a public research index

Only index a public source relevant to named engineering work. Obey robots.txt, remain same-site by default, use conservative concurrency and crawl delay, and do not bypass source protections.

### 1. Plan locally

From the turbo-search repository, create a local plan in its ignored artifacts directory. Set explicit caps no higher than the authorized limits:

```bash
cd /Users/crlough/Code/personal/turbo-search

turbo-search plan "<public-source-url>" \
  --out-dir "artifacts/site-crawls/<source-slug>-plan" \
  --max-pages 3000 \
  --max-chunks 120000 \
  --concurrent-requests 2 \
  --concurrent-requests-per-domain 2 \
  --download-delay 0.5
```

These are conservative crawl defaults. Stricter site requirements, robots directives, or source terms always win.

If the global command is unavailable, substitute `uv run turbo-search`.

Inspect `summary.json`, `plan.json`, `manifest.json`, `chunks.jsonl`, and representative generated `pages/*.md`. Verify:

- the source and canonical URLs are intended,
- discovery is same-site and robots-compliant,
- duplicate, irrelevant, or versioned paths are excluded or explicitly scoped,
- actual planned pages are at most 3,000,
- actual planned chunks are at most 120,000,
- page/chunk samples contain useful engineering material rather than navigation or protected content.

A plan above either authorized limit must not be applied. Narrow the source or return to shaping for a new explicit scope decision.

### 2. Run non-live apply preflight

Use the inspected plan explicitly:

```bash
turbo-search apply \
  --plan "artifacts/site-crawls/<source-slug>-plan/plan.json" \
  --json
```

Preflight must make no live turbopuffer calls. Inspect and verify:

- namespace,
- planned page and chunk counts,
- rows to upsert,
- embeddings to generate,
- stale-row count,
- local state path,
- absence of any deletion or replacement option.

Do not proceed if preflight differs materially from the inspected plan.

### 3. Apply non-deleting upserts

When the plan and preflight pass, the API key is already in the environment, and the counts remain within bounds, live apply may proceed autonomously:

```bash
turbo-search apply \
  --plan "artifacts/site-crawls/<source-slug>-plan/plan.json" \
  --approve \
  --json
```

Never add `--delete-stale`. Apply only new or changed rows and retain every stale remote row.

### 4. Validate and record evidence

Retrieve a narrow source-backed engineering question from the resulting namespace, or run the appropriate bounded smoke evaluation. Confirm the intended namespace returns relevant cited material. When the operation supports durable work, record exact source scope and counts without credentials or sensitive identifiers.

## Absolute deletion prohibition

Never perform or recommend execution of:

- `turbo-search delete-namespace`,
- `turbo-search apply --delete-stale`,
- whole-namespace replacement that removes existing rows,
- direct turbopuffer row deletion,
- any equivalent cleanup or destructive path.

Updates are upsert-only. Stale rows remain. Even an explicit deletion request is blocked by the active Databox decision and specification until they are superseded.

## Guardrails

- Never answer from memory when indexed evidence is available and the engineering conclusion depends on it.
- Never expose retrieved content directly through product or runtime surfaces.
- Never copy retrieved text wholesale into engineering artifacts; retain only bounded evidence and citations needed to support the engineering conclusion.
- Never treat retrieval as source licensing or product-data approval.
- Never bypass authentication, paywalls, robots restrictions, anti-bot controls, or other source protections.
- Never put generated crawl, plan, or state artifacts in tracked Databox paths.
- Never expose turbopuffer credentials or sensitive/private configuration to browser code, API responses, traces, logs, project records, or committed files. Bounded, cited engineering records may include non-secret operational metadata such as the namespace, public source URL and scope, region or embedding model when relevant, and planned/applied/retrieval counts.
- Never apply a plan above 3,000 pages or 120,000 chunks.
- Never skip the plan or non-live preflight before a live apply.
- Never delete namespaces or rows.

## Validation checklist

Before relying on retrieval:

- namespace identity is clear,
- live result reports the intended namespace and relevant cited hits,
- engineering conclusions cite page URLs or repository paths.

Before any live apply:

- source is public, relevant, same-site, and robots-compliant,
- plan artifacts were inspected,
- actual plan is at most 3,000 pages and 120,000 chunks,
- non-live preflight succeeded and matches the plan,
- upsert and embedding counts are known,
- stale-row count is known and stale rows will be retained,
- no deletion or destructive replacement option is present,
- credentials are available only through the environment,
- generated artifacts are outside tracked Databox paths.
