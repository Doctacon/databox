Status: active
Created: 2026-09-05
Updated: 2026-09-10
Parent: None
Depends-On: None

# Support the accepted local primary-warehouse credentials

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `37e46be65122472b6134712ce37b142d5f42aa7f8588d227b952bef04ac0cd7e`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Scope

Support the ratified local `databox-lake-user` long-lived access key and secret without fabricating a session token, while preserving optional temporary OIDC/STS token forwarding, strict catalog-backup token requirements, and a separately owned least-privilege audit.

## Acceptance criteria

- The local primary-warehouse principal and accepted long-lived-key risk are explicitly ratified.
- Compose accepts primary access key plus secret without a session token and forwards the token when temporary credentials provide one.
- Catalog-backup credentials remain distinct and require their temporary session token.
- Existing primary-warehouse access remains least privilege and independently verifiable.
- Documentation records local secret boundaries and the hosted/shared upgrade trigger.

## Explicit exclusions

- Reusing `databox-polaris-catalog-backup` for warehouse access.
- Any long-lived access key other than the separately ratified existing local `databox-lake-user` exception.
- Changing bucket ownership, Iceberg semantics, or disaster-recovery scope.

## References

- `compose.iceberg.yml`
- `.10x/reviews/2026-09-05-first-live-catalog-backup-review.md`
- `.10x/decisions/superseded/catalog-backup-with-rebuildable-iceberg-warehouse.md`

## Evidence expectations

Record the exact principal, Compose behavior for both supported credential shapes, effective-policy audit, validation, and secret-scan result without exposing credentials.

## Progress and notes

- 2026-09-05: Opened after the first live backup proof could restart but not recreate Polaris because `.env` lacked `DATABOX_AWS_SESSION_TOKEN`. The existing container was safely restarted after the backup gate. This did not invalidate catalog backup/WAL proof.
- 2026-09-08: Live identity inspection established that the current primary credentials belong to `databox-lake-user` and are long-lived. The user ratified retaining that local route rather than adding a renewable broker/PKI mechanism. `.10x/decisions/allow-long-lived-local-primary-warehouse-key.md` records the compromise and upgrade trigger. Compose now makes only the primary session token optional while preserving access/secret requirements, temporary-token forwarding, CI OIDC behavior, and mandatory backup-role tokens.
- 2026-09-08: Independent review `.10x/reviews/2026-09-08-primary-warehouse-credential-compatibility-review.md` passed with no findings. Live restored-Polaris validation still must prove the AWS SDK accepts the explicitly blank token.

- 2026-09-10: `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md` owns newly requested same-bucket version protection. Its inspection child `.10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md` MUST reuse this ticket for effective-policy visibility, including lifecycle/versioning/bucket-policy changes and relevant role-assumption bypasses. The user ratified only a new explicit `s3:DeleteObjectVersion` Deny; that statement neither settles other permissions nor closes this broader audit. New authority: `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`.

## Blockers

Audit the effective `databox-lake-user` policy for exact warehouse least privilege. Full live Compose recreation remains separately authorized.
