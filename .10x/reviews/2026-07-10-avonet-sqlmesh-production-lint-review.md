Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Target: .10x/tickets/done/2026-07-10-fix-avonet-sqlmesh-production-lint.md
Verdict: pass

# AVONET SQLMesh production lint and apply review

## Findings

- Exact explicit projection of 38 governed AVONET fields plus two dlt fields removes parse-time external-schema star expansion without changing model output or failure guards.
- Regression coverage rejects future direct AVONET select-star use.
- Pre-apply production diff contained exactly the two reviewed AVONET/catalog models; apply used no unrelated restatement or refresh; post-apply diff is clean.
- Live read-only verification reconciles 10,661 raw rows, 706 catalog taxa, 624 species, 82 hybrids, 600 available species traits, 24 unmatched species, and zero matched hybrids.
- Privacy/location coherence, top-ten bounds, staging cleanup, and absence of persistent `main._dlt*` all pass.

## Verdict

Pass. No blocker remains.

## Residual risk

New external raw schemas must avoid parse-time star expansion unless an explicit external-model schema contract is introduced.
