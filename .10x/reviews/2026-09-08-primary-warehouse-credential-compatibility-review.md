Status: recorded
Created: 2026-09-08
Updated: 2026-09-08
Target: d845d9e
Verdict: pass

# Primary warehouse credential compatibility review

## Findings

None.

## Verdict

Pass. Compose makes only the primary Polaris session token optional while retaining required primary access/secret values, temporary OIDC/STS token forwarding, and mandatory catalog-backup session tokens. Tests cover blank and present primary tokens plus missing backup-token rejection. Documentation and the active decision accurately bound the long-lived-key exception to the local FileVault-protected deployment and identify the hosted/shared upgrade trigger.

## Residual risk

Compose rendering does not prove the Polaris AWS SDK can access S3 with an explicitly blank `AWS_SESSION_TOKEN`; isolated restored-Polaris validation remains the end-to-end proof. The effective `databox-lake-user` policy still requires a least-privilege audit. The long-lived key remains usable until revoked if `.env` or the host is compromised; that local risk is explicitly accepted.
