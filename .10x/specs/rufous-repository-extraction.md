Status: active
Created: 2026-09-03
Updated: 2026-09-03

# Rufous repository extraction

## Purpose

Define a safe extraction of public and private Rufous into `/Users/crlough/Code/personal/rufous` while leaving Databox coherent and passing.

## Repository creation

The destination MUST be a new Git repository with a fresh initial extraction commit. The process MUST NOT modify or delete other sibling repositories. Secrets, `.env`, local databases, caches, build outputs, node modules, generated runtime state, and credentials MUST NOT be copied.

## Extraction behavior

Complete vertical product capabilities MUST move with their implementation, tests, configuration, contracts, models, scripts, documentation, assets, workflows, and governing `.10x` records. Shared code MUST be classified before movement; no private Databox helper may be copied merely to make Rufous pass.

The extraction MUST proceed in bounded reversible slices. Each slice MUST leave its owning repository testable. Databox removal MUST occur only after the corresponding Rufous capability passes in the destination.

Public Rufous production deployment MUST remain fail-closed until the destination workflow supports the new data-product boundary. Existing deployed artifacts MUST remain untouched.

## Required destination surfaces

Rufous MUST own:

- private FastAPI/product APIs and local application state;
- trip planning, catalog, collection, wishlist, alert, calendar, map, and recommendation behavior;
- the React application and artwork;
- product-specific SQLMesh models and Soda contracts;
- public export, audit, hydration, media discovery/review/approval/pinning/publication;
- Cloudflare worker and Pages workflows/configuration;
- product tests, documentation, decisions, specifications, evidence, reviews, and applicable operational instructions.

## Verification

- Rufous provides a credential-free fixture-backed test/demo path.
- Rufous public and private test suites pass independently.
- Databox CI, SQLMesh tests, documentation, and pre-commit pass after removal.
- Search-based residue checks find no active Rufous product implementation or deployment ownership in Databox, except explicit data-product contract references and historical records retained with clear status.
- Search-based coupling checks find no private Databox imports or Databox-relative runtime paths in Rufous.

## Explicit exclusions

- Rewriting Git history.
- Merging either repository branch.
- Enabling production deployment.
- Changing existing product behavior during movement.
- Broad refactoring unrelated to establishing the repository boundary.
