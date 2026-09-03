Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Relates-To: .10x/tickets/done/2026-09-03-transfer-rufous-records-and-docs.md

# Rufous record transfer evidence

## Manifest and authority

The standalone repository contains `https://github.com/Doctacon/rufous/blob/main/.10x/research/2026-09-03-databox-record-transfer-manifest.md`, sourced from Databox revision `572ca6191f598e323161cdadeec3898f10913d31`. It explicitly names 49 active product records moved to their canonical Rufous paths and 283 relevant historical records copied to the clearly non-authoritative `.10x/imported-from-databox/` tree. The manifest also enumerates remain/split classes. Databox retains extraction governance, source/platform contracts, the artifact producer, and provider behavior.

Rufous adds `.10x/README.md` as the cold-start record index and a product-only manual USFWS contract. Databox adds `.10x/knowledge/rufous-record-ownership.md` as its thin pointer. No application implementation changed.

## Documentation

Databox README now describes itself as the artifact-producing platform and points to the standalone consumer rather than documenting application operation. Product navigation was removed from Databox MkDocs; the product runbooks remain temporarily tracked only for deletion by the dependent prune ticket. Rufous README and runbooks are standalone and use repository-local commands.

Generated model documentation is not copied across repositories. Current repositories contain no tracked `docs/models/**`; model inventory regeneration remains repository-local in the prune/aggregate gates.

## Validation

- Exact active and historical path counts agree with the generated manifest.
- `git diff --check` passed in both repositories.
- Secret scans and pre-commit were run in both repositories.
- Residue scans confirm no private Databox import/path in active Rufous source/docs and no Databox README/MkDocs application ownership.

## Review repair

A post-transfer review found that six canonical active Rufous records still expressed the former shared Databox/Quack database architecture. Rufous now has an active standalone data-product boundary decision; the two immutable decisions whose repository/database ownership was superseded moved under `decisions/superseded/`, references were repaired, and the four active specifications now distinguish read-only `RUFOUS_DATABOX_PRODUCT_PATH`/`rufous_inputs_v1` evidence from writable `RUFOUS_DATABASE_PATH` product state. Databox's README no longer contains the leftover trip-plan sentence.

## Residual limitation

Imported historical files and explicitly superseded decisions intentionally preserve original Databox-relative references as provenance; they are non-authoritative and excluded from active-reference validation.
