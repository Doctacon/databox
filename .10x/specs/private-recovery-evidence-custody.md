Status: active
Created: 2026-09-11
Updated: 2026-09-11

# Private custody of original recovery evidence

## Scope and authority

Under `.10x/decisions/keep-recovery-deployment-identifiers-private.md`, preserve original operational records before public redaction. The sole authorized external write root is `~/Private/databox/recovery-evidence/` on the local operator's host. No cloud storage, credential export, synchronization or automatic deletion is added.

## Behavior

- The executor MUST verify FileVault protection and that the destination resolves outside the repository to an operator-owned location. Unknown/disabled protection, unsafe symlinks, unexpected ownership, or inaccessible storage MUST block copying and public redaction; never fix permissions on unrelated files or silently choose another destination.
- New private directories MUST be owner-only (`0700`) and copied files/manifests owner-only (`0600`). Use a new run directory beneath the approved root; never overwrite an earlier evidence bundle.
- Inventory every operational record/text plan selected for public redaction, including affected decisions/evidence/reviews and any affected pending versioning records. Classify committed HEAD originals separately from uncommitted variants. Preserve byte-for-byte originals and verify SHA-256 and byte counts before changing public counterparts.
- Record a private manifest containing source paths, source revision or working-tree provenance, copy paths, digests and verified permissions. Any selected pending record changes needed for lossless branch separation MUST also have a recoverable, explicitly bounded snapshot. Do not sweep up unrelated working-tree data.
- Do not copy `.env`, AWS credential/config caches, `.tfvars`, OpenTofu state, binary plans already privately held, database volumes, warehouse data, personal calendar files, or unrelated `uv.lock` changes. No credential values may enter commands, logs, public records or new manifests.
- Originals and the manifest MUST remain preserved on success and failure. No automatic cleanup, retention deadline, moving/deleting the sole original, or overwriting an existing private file is permitted.
- Public 10x counterparts MUST retain a useful summary, source revision, a refindable generic private-bundle reference and clearly labeled original-artifact digest where applicable. They MUST distinguish redacted text from the exact preserved original; an old plan hash MUST NOT be relabeled as a hash of changed text.

## Acceptance scenarios

- Given a report requiring redaction, copying and digest verification succeed before its public content changes.
- Given a missing/mismatched copy, failed protection check, unexpected existing destination or unsafe ownership, execution stops without modifying the public original or discarding pending work.
- Given committed and uncommitted versions of a record, the manifest distinguishes both and the versioning work remains reconstructible.
- Given a published redacted record, a cold operator can locate the private original and verify its original digest without public disclosure of the redacted identifiers.

## Evidence and limits

Record only public-safe copy counts, permission/protection-check results, source revisions and verified preservation outcomes in 10x. Private manifests stay outside Git. Do not claim cloud backup, immutability or survival of local disk loss. The local operator owns preserved originals; later deletion requires separate explicit authorization.
