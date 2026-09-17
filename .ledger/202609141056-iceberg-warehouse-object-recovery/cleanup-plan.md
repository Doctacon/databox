# Recovery Drill Cleanup Plan

Status: authorized; implementation validation pending

## Purpose

Remove only resources created by the completed recovery drills now that the qualified recovery proof is accepted. Preserve the private evidence under ignored `/.recovery/`, preserve every historical S3 object version, and leave canonical services and protections unchanged.

## Authorized scope

Cleanup may derive exact ownership only from the retained private evidence for:

- Stage 1 synthetic recovery prefixes and retained Docker networks/volumes;
- Stage 2A retained local Docker networks/volumes;
- Stage 2B isolated recovery containers, network, and volume;
- Stage 2C synthetic recovery prefixes and retained Docker networks/volumes.

The cleanup must use one immutable private plan and one durable intent/journal. Current retained runs are bound through their private evidence. Older pre-productization remnants that lack individual receipts may be included only when both their strict generated naming pattern and their exact tool-authored ownership labels identify them as recovery resources. Every resource must match its planned name, immutable identity, ownership labels, configuration fingerprint, and expected attachment state immediately before mutation. Any generated-looking resource with an unknown name or label blocks cleanup.

## S3 boundary

For each exact generated prefix, cleanup may ordinary-delete only a key whose latest version is a live object. This creates one new delete marker. Cleanup must never:

- call `DeleteObjectVersion` or pass a VersionId to deletion;
- remove a delete marker;
- purge or overwrite any historical object version;
- touch a key outside `integration/recovery/<16-character-run-id>/stage1/warehouse/`;
- alter versioning, lifecycle, bucket policy, encryption, ownership, ACL, public-access controls, or IAM.

Before and after each delete, the complete bounded timeline must prove that all prior versions remain exact and that the sole change is one new latest delete marker.

## Docker boundary

Cleanup may stop and remove only exact evidence-owned Stage 2B isolated containers. It may then remove exact evidence-owned drill networks and volumes only after proving there are no unapproved consumers or attachments. It must not use force removal, inspect or remove active Compose resources as cleanup targets, or remove an ownership-mismatched resource.

The active PostgreSQL and Polaris services must be healthy before cleanup and remain the same healthy resources afterward.

## Evidence and completion

Existing private evidence remains in `/.recovery/`. The cleanup plan, intent, journal, and result are private files with mode `0600`. Public output and the ledger outcome contain only sanitized counts and conclusions.

Success requires:

1. no live current object remains under any planned synthetic prefix;
2. all pre-cleanup historical versions remain present;
3. every planned drill Docker resource is absent;
4. active PostgreSQL and Polaris remain unchanged and healthy;
5. bucket versioning, lifecycle, and retention-policy protections remain intact; and
6. source evidence remains unchanged.

A terminal result consumes the plan. Cleanup does not authorize another recovery drill, negative IAM test, cutover, or deletion of private evidence.
