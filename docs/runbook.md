# Operations runbook

Finite validation commands only; `task dagster:dev` starts a long-running UI and
must be stopped with Ctrl-C.

## Rebuild local warehouse from sources

```bash
task db:reset
task full-refresh
```

`task full-refresh` validates the configured Polaris catalog and AWS S3 writer,
launches every source marked `parallel_refresh=True` concurrently as an
independent Dagster job, verifies each authoritative Iceberg table and explicit
`_dlt_load_status`, then runs project-wide native SQLMesh and every Soda contract
only if the preceding phase succeeded.
`SOURCE_START`/`SOURCE_END` lines and Dagster run IDs attribute interleaved logs;
overlap is calculated from timestamps around each source's `dg launch`
subprocess, proving worker-process overlap while including subprocess startup
time. Raw data lives in S3-backed Iceberg tables registered by Polaris;
`data/databox.duckdb` contains the local SQLMesh schemas such as
`environmental_observations` and `analytics`.

Before refreshing, configure the Polaris client, AWS region, S3 bucket, and AWS
runtime credentials documented in `.env.example`. Leave the session token empty
for the accepted local long-lived key; provide its paired token for temporary
OIDC/STS credentials. `databox_lake` must already be provisioned with
`s3://<bucket>/warehouse` as its base location and the bucket-scoped IAM role,
then start `compose.iceberg.yml`.

PostgreSQL first reports only basic database liveness. Polaris bootstrap then
initializes the schema and realm. The one-shot `catalog-backup-readiness` service
validates the primary runtime AWS credential against the separate pgBackRest
repository and stanza, a WAL archive round trip, and an existing or newly created
post-bootstrap full backup. The Polaris API remains stopped when any check fails;
inspect the backup-readiness service output rather than bypassing protection.

Static pinned AVONET is deliberately excluded from routine refresh. Run its
independent `avonet_ingest` Dagster job explicitly when a validated
`raw_avonet.species_traits` replacement is required; it has no recurring
schedule. The job preserves the pinned file/hash/schema checks and publishes the
complete validated snapshot directly as a dlt-managed Polaris Iceberg table.

## Smoke verification

```bash
task verify
cd transforms/main && ../../.venv/bin/sqlmesh test
```

`task verify` uses `DATABOX_SMOKE=1` with the same concurrent Polaris Iceberg
source path, then runs the same project-wide SQLMesh and Soda phases.

## Protected live integration

The GitHub workflow `.github/workflows/polaris-iceberg-integration.yaml` is a
manual, protected diagnostic gate rather than a durable refresh. Each of the six
routine sources gets an independent job, disposable Polaris/Postgres state, and
`integration/<run>/<attempt>/<source>/warehouse` S3 prefix. It uses GitHub OIDC;
do not add static AWS credentials or automatic PR/push/schedule triggers.

Dispatch it from the GitHub Actions UI, approve the
`polaris-iceberg-integration` environment, and inspect every matrix result. The
workflow skips SQLMesh and does not delete integration objects. The first
complete passing matrix was recorded on 2026-09-03; inspect the protected
workflow's current GitHub Actions run for exact claims and limits.

## Plan recovery infrastructure

Recovery infrastructure is declared in `infra/recovery/` with OpenTofu
`>=1.8,<2`. It creates one same-account, same-region catalog-backup bucket for
pgBackRest. The accepted same-account and `us-west-1` design does not protect
against account-wide or regional failure. Iceberg warehouse objects are not
copied: use Iceberg snapshots for logical rollback while objects remain, and
rebuild complete warehouse loss from canonical sources.

Copy `infra/recovery/terraform.tfvars.example` to an ignored `.tfvars` file and
replace every placeholder. Configure `aws_profile` in an AWS shared config file with renewable
credentials; do not put credentials in OpenTofu variables or state. OpenTofu
declares the console-only `databox-recovery-operator` user without an access
key, login profile, password, or MFA seed. Its inline policy permits only
assuming the bucket-scoped catalog-backup role and the two OAuth actions AWS
requires for `aws login --remote`, scoped to the account's `us-west-1` remote
public client. It cannot use same-device login or other sign-in clients. After
its separately reviewed apply, root
must manually enable console access and MFA for that user; passwords, recovery
codes, and MFA secrets must never enter OpenTofu configuration or state. The
human then uses `aws login --remote --profile databox-recovery-operator --region us-west-1`
for the operator source profile and an AWS CLI role
profile configured with `role_arn`, `source_profile`, and `mfa_serial`. The
human enters MFA when calling `AssumeRole`; AWS returns ordinary short-lived
role credentials for host injection, and pgBackRest never receives MFA data.

A separate declared inline policy, `databox-warehouse-writer-inspection`, grants
that operator five IAM read/list actions against only `databox-lake-user` in
`var.aws_account_id`: GetUser, ListUserPolicies, GetUserPolicy,
ListAttachedUserPolicies, and ListGroupsForUser. It does not grant managed-policy
document, group-policy or role-policy reads.

The user explicitly abandoned a prepared but unapplied stage-2 operator grant
and chose the root-backed profile for the remaining bounded warehouse-recovery
audit and infrastructure work, deferring deployer-role design until afterward.
Keep raw IAM documents and identifiers private. Root use does not remove the
fresh exact-plan review and explicit apply gate for warehouse changes.

The deployed inspection policy does not change the existing login policy,
backup-role permissions, or warehouse bucket settings. It is not a complete
effective-permission audit: boundaries, group policies, relevant role policies,
cross-account references, resource policies, SCPs, session constraints, or
other restrictions must remain explicit where unverified.

Manage this grant through `aws_iam_user_policy.warehouse_writer_inspection` in
this root, not by editing the console's existing Terraform-named policy. If a
same-named inspection policy was already created manually, stop before apply and
reconcile ownership with separately authorized import or removal; do not silently
overwrite it. Remove the inspection grant through a reviewed infrastructure
change when its purpose is complete, preserving the operator's existing access.

`var.aws_account_id` remains the single account input for both the policy ARN
and the provider's account guard. OpenTofu does not automatically read
`DATABOX_AWS_ACCOUNT_ID` from `.env`; if that local value is maintained as well,
confirm it matches the selected tfvars account before planning. A browser root
login does not authenticate the CLI profile. For the current user-approved
exception, use an explicitly authenticated root-backed CLI session for the
remaining audit and separately approved plan/apply operations, then log it out.
Never create root access keys for this workflow.

Review only—these commands do not apply infrastructure:

```bash
cd infra/recovery
tofu init -backend=false
tofu fmt -check
tofu validate
tofu plan -var-file=recovery.auto.tfvars -out=recovery.tfplan
```

`plan` is a saved live-refresh plan: it evaluates provider configuration,
reads current managed-resource state, and requires the configured AWS profile.
Review any reported drift separately; do not hide it with `-refresh=false`.
Do not run `tofu apply` until the exact saved plan is reviewed and separately
authorized. OpenTofu does not create, own, replace, destroy, relocate, or rewrite
the primary Iceberg bucket; it declares only that existing bucket's policy,
versioning setting, and lifecycle configuration.

OpenTofu state is intentionally local and operator-owned at
`infra/recovery/terraform.tfstate`; always run init, plan, apply, and import from
`infra/recovery/`. State and plan files are ignored by Git, and state must remain
mode `0600` on the FileVault-protected host. A second backup copy is not required;
the operator accepts manual state reconstruction after disk loss. Project cleanup
commands must never delete these files. If state is lost, stop all changes and
use reviewed `tofu import` commands for every existing resource, followed by a
reviewed refresh-only plan; never recreate or apply over untracked live resources.

All recovery plans, journals, raw command exports, and receipts belong under the
ignored `/.recovery/` custody root with private file permissions. Never force-add
raw recovery evidence; publish only reviewed, sanitized summaries under
`.ledger/` or durable documentation.

## Warehouse object-version protection

`warehouse_bucket` is a required, private `recovery.auto.tfvars` input naming the
existing warehouse bucket. Before plan/apply, verify it equals the local
`DATABOX_AWS_S3_BUCKET`, differs from `catalog_backup_bucket`, is in the expected
account/region, and has no newly appeared lifecycle or bucket policy. Terraform
also checks that the active caller ARN is the exact account-root ARN before it
reads the warehouse target; repeat that identity check immediately before apply
because a saved plan does not pin credentials. Enabled/suspended or externally
managed versioning, or any lifecycle/policy document, requires ownership
reconciliation and possibly a separately approved import; never overwrite it
blindly. Do not add a
warehouse-bucket resource or output, and keep the private tfvars file mode `0600`.

The warehouse policy is a temporary root-only **retention-control** boundary. It
contains no Allow and exactly two Denies with `Principal = "*"` plus
`ArnNotEquals` on `aws:PrincipalArn` against only the exact account-root ARN:

- deny `s3:DeleteObjectVersion` on warehouse objects;
- deny `s3:PutBucketVersioning`, `s3:PutLifecycleConfiguration`,
  `s3:PutBucketPolicy`, and `s3:DeleteBucketPolicy` on the bucket.

[AWS documents](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-principalarn)
that `aws:PrincipalArn` contains the IAM role ARN for role sessions and the exact
root-user ARN for account-root requests. The policy therefore
covers direct users, the known writer-assumable role, and unknown same- or
cross-account role sessions while leaving actual account root as the temporary
control identity. Do not substitute `NotPrincipal`, add a service exception, or
broaden the root exception. A future non-root deployer must first be added to the
exception through a separately reviewed root change.

State the guarantee narrowly: non-root principals cannot manually purge named
versions or weaken/remove these three retention controls. Ordinary `PutObject`
and `DeleteObject` remain available through existing identity policies; with
versioning, an ordinary delete normally creates a delete marker. Non-root
principals that can read a historical version and write an object can still
promote that content as a new current version. Root and S3 Lifecycle remain
intentional permanent-deletion paths. Bucket deletion, Object Lock, unrelated
bucket security settings, current-object corruption, version storms, storage
cost, root/account compromise, and losses detected after expiration are outside
this guarantee.

Enable versioning bucket-wide, then configure exactly one bucket-wide lifecycle
rule expiring noncurrent versions after 30 days. Do not add current-version
expiration, transitions, delete-marker cleanup, newer-version count, multipart
cleanup, or Iceberg maintenance. [Lifecycle expiration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html)
is not blocked by the bucket-policy Deny. Thirty days starts when a version
becomes noncurrent and is UTC-rounded/asynchronous, not immutable retention or a
guaranteed 720 hours.
Existing null versions gain no retroactive history; after their next overwrite or
delete, the null version becomes noncurrent and enters lifecycle handling.

Immediately before a saved live-refresh plan, re-read policy, lifecycle, and
versioning and stop if any expected-absent singleton appeared. A clean declaration
expects three creates—warehouse policy, versioning, and lifecycle—with all catalog
and IAM resources no-op and no output change. Keep the plan/log mode `0600`,
inspect resolved JSON privately, hash the exact binary and inputs, and obtain
explicit approval. Do not use `-refresh=false`.

Before apply, a named maintenance owner must confirm PUT/DELETE traffic is quiet
across all three prefixes. Recheck the exact target, root identity, saved-plan
hash/fingerprints, and absent live singletons; apply only the approved binary.
After versioning reads back `Enabled`, keep every write path paused for a fresh
full 15 minutes, per [AWS's first-enablement guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/versioning-workflows.html), while verifying policy,
lifecycle, public-access block, AES256 encryption, BucketOwnerEnforced ownership,
and unrelated settings. On partial failure, preserve the pause and diagnostics;
do not suspend versioning, delete controls, destroy resources, or retry blindly.

This protection preserves prospective object history only. It does not recover
objects already lost, prove a denial, or prove coherent Iceberg recovery. Those
claims require a separately approved disposable-table drill that aligns catalog,
metadata, manifests, data/delete files, and query results.

## Real Iceberg object-recovery drill

`scripts/platform/iceberg_recovery_drill.py` is one manual Stage-1 drill. It is
never scheduled and never uses the active Polaris service. Each run derives a
private Docker network, PostgreSQL volume, transient PostgreSQL/bootstrap/Polaris
containers, generated catalog/namespace/table, and
`integration/recovery/<run-id>/stage1/warehouse/` S3 scope from one random token.
Canonical catalogs, tables, volumes, services, and `warehouse/` remain outside
its accepted names.

The CLI has two commands but two independently approved mutation plans.
`prepare` is mutation-free: it reads local configuration, inspects already
installed Docker images/runtime without pulling or building, pins exact image
IDs, launch/default-environment/user/working-directory configuration, and atomically
writes a private Seed-A plan. It does not call AWS, S3, Polaris, or a Docker
create/start/remove operation. Plan and initial-journal publication is atomic
no-replace: an existing or concurrently published receipt is never overwritten.

```bash
task iceberg:recovery-drill:prepare
```

Privately inspect `.recovery/iceberg/<run-id>/seed-a.plan.json`, verify its exact
SHA-256, and obtain separate explicit approval before seed execution. Then use
the same generic executor with exactly that reviewed filename/hash:

```bash
task iceberg:recovery-drill:execute -- \
  --manifest .recovery/iceberg/REPLACE_RUN_ID/seed-a.plan.json \
  --sha256 REPLACE_APPROVED_SEED_SHA256
```

Seed execution resolves the approved profile once to one temporary credential
set, verifies that exact set with STS against the normalized non-root caller
digest, and reuses it for every direct S3 call and Polaris bootstrap. It never
re-resolves the profile during the run. It also rechecks source/runtime/image
pins, bucket owner/region, Enabled versioning, the single bucket-wide 30-day
noncurrent rule, the exact two-Deny/root-exception policy, empty generated prefix,
and absent resource collisions before mutation. It creates only the
plan-named network/volume and transient secret-bearing containers. PostgreSQL,
Polaris, and temporary AWS credentials are passed to bounded child processes
through stdin, never command arrays, plans, Docker environment configuration, or
stdout. Seed-A runs a versioning canary with the pinned credential set for
put/ordinary delete and exact historical-version read/promotion. Recovery-A
repeats that canary with its newly exported, STS-verified credential set after
fresh point-A validation and immediately before publishing the damage marker.
Restore-only re-entry never reruns the canary or continues damage.

The isolated catalog then receives one deterministic three-row Iceberg v2 table.
The script requires every catalog-loaded FileIO to contain nonempty Polaris-vended
access, secret, and session credentials, fences every FileIO operation before
access, captures the metadata → manifest-list → manifest → data graph, and records exact VersionIds,
ETags, sizes, and SHA-256 values. It rejects null versions, external locations,
non-point-A entries, more than 64 objects, more than 32 MiB before body download,
or insufficient version-count headroom. Secret-bearing containers are removed
before the retained network/volume inspection state is fingerprinted and the atomic
`manifest.json` Recovery-A plan is written; the labeled network, PostgreSQL volume,
private plans, generated catalog state, and S3 history remain.

Seed success does not authorize damage. Privately inspect the resulting
Recovery-A filename/hash and obtain a second explicit approval:

```bash
task iceberg:recovery-drill:execute -- \
  --manifest .recovery/iceberg/REPLACE_RUN_ID/manifest.json \
  --sha256 REPLACE_APPROVED_RECOVERY_SHA256
```

Recovery execution rechecks the Recovery-A/Seed-A relationship, settings,
identities, images, exact retained network/volume fingerprint, catalog fingerprint,
point-A pointer, every current source version, and all content before damage. It
inventories all running/stopped exact-name containers, retained-network attachments,
and retained-volume consumers. Only ID-bound PostgreSQL/Polaris sleeper remnants
with the exact pinned launch, environment, labels, mount, privilege, and loopback
port contract may be removed; bootstrap, changed, unknown, or volume-only consumers
are refused. It starts only transient containers against the run-owned PostgreSQL
volume after proving that volume unused. A per-key,
mode-`0600`, atomically replaced and fsynced `damage-started.json` records delete
and promotion intent plus observed VersionIds. Ordinary deletes run leaves first
and metadata root last; break proof requires a healthy namespace, exact approved
missing-object failure, current markers, and independently readable historical
sources. Restoration promotes each exact source version, verifies the new
current bytes/version while preserving the source, and then requires the exact
UUID, pointer, snapshot, logical graph, schema, rows, count, and digest.

After the journal exists, rerunning the same Recovery-A command is restore-only,
even if its six-hour first-damage approval window has expired. An expired plan with
no exact bound journal contains any fully validated credential-bearing remnants and
then stops before AWS preflight or damage. Resume never deletes; it accepts only
journal-attributable markers/promoted versions, refuses unknown current state, and
reports `recovered-after-interruption` instead of `pass`. Exact owned recovery
remnants may be contained before restart; unknown resources are refused.
Transient containers are removed on success or caught failure, while network,
volume, catalog evidence, plans, object versions, markers, and restored current
objects are preserved.

Configure one explicit profile name and canonical caller hash in ignored `.env`.
The already-authenticated non-root profile must be in the same AWS account as
`DATABOX_RECOVERY_STORAGE_ROLE_ARN` and is used for both ordinary-delete and
exact-version recovery operations. The project-wide `DATABOX_AWS_ROLE_ARN`
remains unchanged. The operator may be an IAM user or assumed role; the separately
plan-bound dedicated Stage-1 role remains Polaris's vended-credential role. Also
generate one private run-secret of at least 32 random characters; only run-scoped
HMAC-derived PostgreSQL/Polaris credentials exist in memory and only an HMAC
binding is saved. The script never logs in or prints caller identities/credentials.

```dotenv
DATABOX_RECOVERY_STORAGE_ROLE_ARN=
DATABOX_RECOVERY_PROFILE=
DATABOX_RECOVERY_IDENTITY_SHA256=
DATABOX_RECOVERY_RUN_SECRET=
```

Generate the caller hash privately from canonical `get-caller-identity` output.
The projection normalizes an assumed-role session ARN to its durable IAM role ARN,
so a normal session refresh cannot strand restore-only recovery:

```bash
profile=REPLACE_EXPLICIT_PROFILE
aws --profile "$profile" sts get-caller-identity --output json --no-cli-pager \
  | .venv/bin/python -c '
import hashlib, json, re, sys
identity = json.load(sys.stdin)
arn = identity["Arn"]
assumed = re.fullmatch(
    r"arn:(aws(?:-us-gov)?):sts::([0-9]{12}):assumed-role/(.+)/[^/]+", arn
)
if assumed:
    arn = f"arn:{assumed[1]}:iam::{assumed[2]}:role/{assumed[3]}"
payload = json.dumps(
    {"account": identity["Account"], "arn": arn},
    sort_keys=True,
    separators=(",", ":"),
) + "\n"
print(hashlib.sha256(payload.encode()).hexdigest())
'
```

This Stage-1 run proves reconstruction, not separate-principal privilege
separation; that stronger proof is explicitly out of scope for the solo workflow.
The script strips ambient AWS/profile/web/container/legacy-boto providers and
HTTP proxies before PyIceberg is constructed, rejects AWS account root, fences
all direct S3 calls with the expected bucket owner, and refuses IAM broadening or
fallback. It never calls `DeleteObjectVersion`, removes a marker, alters bucket
controls, guesses metadata, drops the catalog, or removes the retained network or
volume. Cleanup is separate, non-purging, unimplemented, and requires its own
reviewed exact plan and approval.

This proves coherent object reconstruction only for one constrained synthetic
Iceberg v2 table with its isolated catalog pointer intact. It does not prove catalog PITR,
negative policy enforcement, arbitrary-table recovery, bucket/account recovery,
or recovery after lifecycle expiration.

## Stage 2A: local POSIX catalog PITR

Run the synthetic, cloud-free proof with:

```bash
task catalog:recovery-stage2a
```

It creates only generated Docker resources, bootstraps the real Polaris relational
schema, writes deterministic point-A state, takes a POSIX pgBackRest backup,
commits later point-B state, and restores a separate PostgreSQL volume to a named
target. Success requires point A to exist, point B to be absent, PostgreSQL to be
promoted, and Polaris readiness against the recovered schema. Credential-bearing
containers are removed; the generated network, source/restored volumes, POSIX
repository volume, and ignored mode-`0600` result are retained. It never contacts
AWS or active services, reads canonical data, cuts over, or cleans up resources.

The deployed S3 backup repository, authenticated WAL catch-up, canonical catalog
validation, and production RPO/RTO belong to separately authorized Stage 2B.

## Stage 2C: joint isolated catalog and warehouse recovery

Stage 2C composes local POSIX catalog PITR with exact-version recovery in the real
versioned warehouse sandbox. It is limited to exactly two generated tables under
`integration/recovery/<run-id>/stage1/warehouse/`, one point-A backup/target, one
point-B append per table, at most 64 keys and 32 MiB, and one damage cycle. It
never uses active/canonical services, the deployed catalog-backup repository or
credentials, root, IAM changes, cutover, version purging, or automatic cleanup.

Prepare a mutation-free private campaign plan, then execute only that exact plan:

```bash
task catalog:recovery-stage2c -- prepare
task catalog:recovery-stage2c -- execute \
  --plan .recovery/catalog-warehouse-stage2c/<run-id>/campaign.plan.json \
  --sha256 <exact-private-plan-sha256>
```

The success path has a 20-minute objective. Every child operation is individually
bounded; after the durable damage journal exists, deadline expiry enters mandatory
restoration and containment rather than abandoning damaged objects. Re-entry is
restoration-only. Generated Docker resources are accepted or removed only after
exact campaign-bound image, label, mount, network, port, attachment, and volume-
consumer checks. Final success requires both restored catalog pointers, UUIDs,
snapshots, logical graphs, schemas, and deterministic rows to match point A while
point-B-only objects remain unreferenced. All generated resources and private
evidence are retained.

The first authorized live campaign stopped before point A because its ownership
validator did not distinguish Docker's empty configured ephemeral host port from
the numeric runtime loopback assignment. A later authorization allowed three
fresh attempts with at most one damage-bearing cycle. The first two stopped
contained before damage. The third completed deletes and break proof, then stopped
during catalog restoration because Docker represents `--network none` as a built-
in runtime network entry rather than an empty network map. Exact object restoration
completed automatically; after correcting that fail-closed validator, mandatory
catalog restoration and containment also completed and were independently checked.

That campaign is **not** a Stage-2C success: final joint Polaris pointer, graph,
schema, and row validation did not run after the terminal failure. All generated
containers are absent, while prefixes, networks, volumes, and private evidence are
retained. Every plan is consumed, the three-attempt envelope and one damage cycle
are exhausted, and no fresh live execution is authorized. Do not replay any plan
or infer success from the post-failure restoration receipt.

Two runtime details are now explicit in the maintained implementation. After
PostgreSQL is restarted into archival mode for the point-A backup, source Polaris
is recreated and the cached gateway is discarded so its JDBC pool and ephemeral
loopback endpoint cannot remain stale. A restore helper is accepted only on
Docker's built-in `none` network with no aliases, DNS names, addresses, gateways,
or MAC address; any connected shape is rejected.

A separately authorized validation-only continuation can complete the missing
final read against that exact restored retained state without replaying recovery:

```bash
task catalog:recovery-stage2c -- prepare-validation \
  --plan .recovery/catalog-warehouse-stage2c/<run-id>/campaign.plan.json \
  --sha256 <exact-original-campaign-plan-sha256>
task catalog:recovery-stage2c -- validate \
  --plan .recovery/catalog-warehouse-stage2c/<run-id>/validation.plan.json \
  --sha256 <exact-validation-plan-sha256>
```

The validation plan hash-binds the campaign, recovery plan, damage journal,
terminal failure, restoration correction, detached Docker resource projections,
and exact bounded-prefix version timelines. Validation starts only the retained
restored PostgreSQL volume with archival disabled and the restored Polaris service;
it never runs backup/restore or changes warehouse objects. It is one-shot and has
a ten-minute objective plus per-command bounds. A separate watchdog removes
credential-bearing containers on objective expiry; this is not a hard whole-process
or RTO claim. Interrupted re-entry performs Docker-only containment without current
AWS credentials, source/image freshness, or plan-expiry gates and never revalidates.
Success proves eventual point-A catalog/warehouse coherence, point-B exclusion, and
unchanged object-version timelines. It does not rewrite the original terminal
evidence or claim uninterrupted recovery or the 20-minute RTO.

The retained validation invocation described here is now consumed and must not be
replayed. Its substantive promoted-version and two-table Polaris checks passed, but
the command stopped `failed-contained` at a later inventory predicate that compared
new promoted-copy ETags with historical-source ETags. Read-only diagnosis found all
19 expected keys, unchanged exact timelines, exact current bytes, and intact source
versions; only the four promoted ETags differed. Because ETag is version metadata,
not the cross-version content identity, the maintained inventory check now verifies
exact SHA-256/size plus recorded source/promoted VersionIds instead. The append-only
adjudication supports eventual coherent recovery only; the validation command,
original automation, and RTO remain unproven.

## Recovery-drill cleanup

Cleanup is a separately authorized, one-shot terminal operation. It retains private
`/.recovery/` evidence, ordinary-deletes only live objects under exact generated
drill prefixes, and removes only exact ownership-validated drill Docker remnants.
Ordinary deletion creates new delete markers; it never deletes object versions or
removes markers. Canonical resources, active Compose services, bucket controls,
IAM, and the deployed backup repository are outside its mutation scope.

```bash
task recovery:cleanup -- prepare
task recovery:cleanup -- execute \
  --plan .recovery/cleanup/<run-id>/plan.json \
  --sha256 <exact-plan-sha256>
```

Preparation is read-only apart from its private mode-`0600` plan. Execution first
rederives the complete authorized inventory, requires unchanged source evidence,
exact S3 timelines, exact Docker identities/configuration/attachments, healthy
active services, and the approved bucket protections. It durably writes intent
before mutation, immediately rechecks each target, uses no force removal, and
publishes a private terminal result. Public output contains counts only. A terminal
plan cannot be replayed. Cleanup does not authorize another drill, RTO rehearsal,
negative IAM test, cutover, or deletion of private evidence.

## Catalog backup and recovery preparation

The PostgreSQL image includes pgBackRest and archives WAL with
`archive_timeout=300s`. pgBackRest reuses the primary `DATABOX_AWS_*` runtime
credential: the local `databox-lake-user` credential has no session token, while
CI's temporary OIDC credential includes one. The catalog-backup bucket policy
grants these runtime principals only the bucket/object operations pgBackRest
requires and denies non-root version deletion and protection changes. Production
uses repository path `/polaris`; protected CI sets a run/source-isolated path.
Configure the OpenTofu catalog-backup output and `PGBACKREST_REPO1_CIPHER_PASS`; never
commit or log runtime secrets. The MFA-protected catalog-backup role remains for
human recovery and is not injected into routine containers. The PostgreSQL image
does not install AWS CLI or mount host AWS profiles. The production repository
path remains `/polaris`.
Run `task catalog:backup-check` before the weekly `catalog:backup-full` or daily
`catalog:backup-diff`, and inspect `task catalog:backup-info` after each run. All
four manual commands execute pgBackRest as the container's `postgres` user.
These commands are not scheduled automatically and do not prove the recovery
objectives.

Prepare—do not execute—an isolated restore with a new Docker volume name:

```bash
uv run python scripts/platform/catalog_recovery.py \
  --target-volume databox_polaris_recovery_20260905 \
  --active-volume databox_polaris_postgres \
  --recover-to 2026-09-05T12:00:00Z \
  --prepare-only
```

Preparation rejects the active volume, malformed names or timestamps, missing
backup settings, and any target volume that already exists. It creates no volume
or container. The explicit `--execute` path is implemented but requires separate
live-restore authorization; it creates the target, initializes only its ownership,
and runs the pinned pgBackRest image as `postgres` with secret values inherited
by environment-variable name. It mounts no active volume or socket, opens no
port, never removes the target on failure, and stops before PostgreSQL or Polaris
startup, validation, or cutover.

For a separately authorized complete timed drill, run the existing recovery
entrypoint from an interactive operator terminal:

```bash
task catalog:recovery-drill -- \
  --catalog databox_lake \
  --source-revision "$(git rev-parse HEAD)"
```

The command normally performs one AWS remote login and MFA-protected role export
on the operator TTY. When the operator has just completed that login and primed
the backup-role session in the same AWS CLI configuration, pass
`--reuse-authenticated-session` to skip only the redundant login prompt; the
command still exports the short-lived role session directly into memory and
refuses credentials with less than 15 minutes remaining. That minimum prevents
near-expiry cache reuse; it does not guarantee the 60-minute RTO objective.
Before creating a marker, it enumerates every locally retained
`.ready` WAL file, validates the bounded list and corresponding regular files,
and synchronously uploads every segment oldest-first with the same session. It
never renames or deletes WAL or archive-status files. After switching and pushing
the marker segment, it derives a bounded same-timeline sequence from the segment
before the oldest pending file through the marker and synchronously retrieves each
segment from the repository into one exact `/dev/shm` verification path. pgBackRest
validates each retrieved segment and the command removes only that transient path;
any missing segment or cleanup failure stops before restore. This catch-up does not
retroactively protect changes that existed only on the local machine before the
command ran.

Temporary credentials are never written to `.env`, a handoff file, or preserved
container configuration. Recovery PostgreSQL starts inside a secret-free sleeper
container and receives backup credentials only in its first detached child process
while PITR fetches WAL. After promotion and marker validation, the container is
stopped, restarted, and PostgreSQL is launched again without backup credentials;
any earlier failure stops the credential-bearing process. Polaris follows the same
secret-free sleeper pattern, receives credentials only in a detached child process,
and is always stopped after validation or failure while its container remains
preserved. The command uses a microsecond-precise marker bracket,
synchronous marker and cleanup WAL pushes, a new ownership-labeled volume,
unexposed archive-disabled PostgreSQL, no-bootstrap Polaris, and the registry-derived
validator. Its report records pending count, oldest/newest segment, oldest pending
mtime and age at command start, ordered uploads, observed repository maximum,
continuity anchor/verified-through marker, and the marker target-inclusion gap. The
observed maximum is informational and is never treated as continuity proof; the
report does not label the marker gap as continuous RPO.
End-to-end RTO starts before authentication, and a result over 3,600 seconds exits
nonzero. It never restarts the active stack, cuts over, or deletes recovery resources.

After separately authorized restored PostgreSQL and Polaris startup, validate
only the explicitly named no-port recovery container:

```bash
uv run python scripts/platform/catalog_recovery_validate.py \
  --polaris-container databox-polaris-recovery-validation-20260908-214022 \
  --catalog databox_lake \
  --recovery-target 2026-09-08T21:40:22Z \
  --source-revision e27990e
```

The validator resolves `--source-revision` to a commit and fails unless that
commit's canonical registry bytes exactly match the imported working-tree
registry. The example uses the reviewed corrected validation-contract revision;
record the distinct historical code revision for the selected recovery point in
the drill evidence. It derives every expected raw table and per-source
`_dlt_load_status` from `databox.config.sources.SOURCES`. It rejects a container
that lacks the recovery-validation label, is stopped, or publishes a host port.
It enumerates the restored catalog, loads every expected table with
Polaris-vended credentials, requires a current snapshot, plans its manifests,
and performs a read-only limit-one data scan. Empty tables pass when that path
completes with zero rows. Output is bounded and secret-free. Missing, malformed,
unreadable, or undeclared tables inside canonical namespaces exit nonzero.
Namespaces and tables outside the canonical registry remain prominent warnings
and do not fail recovery by themselves; they are never silently allowlisted or
deleted. The validator never contacts the active catalog, bootstraps, writes,
refreshes sources, cuts over, or cleans up recovery artifacts. Run it only after
separately authorizing the exact recovery target and container.

A bad table publication should use a validated Iceberg snapshot rollback while
its objects remain. Complete primary-warehouse loss requires source rebuild and
is not covered by the 60-minute catalog RTO. Last-resort table registration must
use a validated metadata location, never lexicographic S3 listing. Live PITR
execution and the timed catalog RPO/RTO drill remain separately authorized work.

## SQLMesh dev loop

```bash
cd transforms/main
../../.venv/bin/sqlmesh plan dev --auto-apply --no-prompts
../../.venv/bin/sqlmesh test
```

Dev schemas use the `__dev` suffix, for example
`environmental_observations__dev.fact_bird_observation`.

## CDM row-count sanity checks

```sql
SELECT COUNT(*) FROM environmental_observations.fact_bird_observation;
SELECT COUNT(*) FROM environmental_observations.fact_weather_observation;
SELECT COUNT(*) FROM environmental_observations.fact_streamflow_observation;
SELECT COUNT(*) FROM environmental_observations.fact_earthquake_event;
SELECT COUNT(*) FROM analytics.platform_health;
```

Primary key duplicate checks should return zero:

```sql
SELECT COUNT(*) - COUNT(DISTINCT bird_observation_sk)
FROM environmental_observations.fact_bird_observation;

SELECT COUNT(*) - COUNT(DISTINCT weather_observation_sk)
FROM environmental_observations.fact_weather_observation;

SELECT COUNT(*) - COUNT(DISTINCT streamflow_observation_sk)
FROM environmental_observations.fact_streamflow_observation;

SELECT COUNT(*) - COUNT(DISTINCT earthquake_event_sk)
FROM environmental_observations.fact_earthquake_event;
```

## Broken local file recovery

```bash
mv data/databox.duckdb data/databox.duckdb.broken
task full-refresh
```

If the rebuild fails, restore the backup and inspect `.logs/` plus Dagster run
history under `.dagster/`.

## Rollback SQLMesh prod

SQLMesh plan history is the rollback mechanism:

```bash
cd transforms/main
../../.venv/bin/sqlmesh state list
../../.venv/bin/sqlmesh plan prod --restore-from <previous-plan-id> --auto-apply
```

## UI launch

```bash
task dagster:dev
```

This command is intentionally long-running. Stop it with Ctrl-C after manual UI
inspection.
