Status: active
Created: 2026-07-10
Updated: 2026-07-10

# Personal bird collection

## Purpose and scope

This specification governs local manual observation events, derived life-list membership, wishlist state, and watch definitions for the single local user. It uses `birding_agent.arizona_species_catalog.species_code` as taxon identity and never creates an account or remote profile.

## Data ownership and model

Runtime-owned physical DuckDB tables MUST store personal state separately from SQLMesh models:

- observation: immutable ID, species code, observation date, optional location text, optional notes, created/updated UTC timestamps;
- wishlist: species code plus created UTC timestamp, unique by species code;
- watch: species code, active state, Arizona center latitude/longitude plus display name, radius miles, created/updated UTC timestamps, unique by species code.

Observation date is a calendar date and MUST NOT be reinterpreted as a timestamp. Location and notes are user text, not evidence or geocoding claims. Text MUST be trimmed and bounded; empty optional text becomes null. Personal state persists until explicit mutation.

Every mutation MUST validate that the species code exists in the exact current Arizona catalog. Hybrids are valid identities. A later catalog refresh MUST NOT silently rewrite or delete existing personal rows; missing-current-catalog references remain visible with a clear stale-identity state until the user edits or deletes them.

## Observation behavior

- Create MUST require species code and observation date; location and notes are optional.
- Edit MUST allow species code, date, location, and notes to change atomically after validating the target species.
- Delete MUST permanently remove exactly one observation after explicit confirmation in the UI.
- IDs and created timestamps MUST remain stable across edits. Observation and watch `updated_at` MUST advance strictly on every actual mutation even if the process clock is equal to or earlier than the persisted timestamp.
- Listing MUST use observation date descending, updated timestamp descending, and ID as a stable tie-break.
- Life-list membership MUST be derived from at least one remaining observation. It MUST expose first-observed date, latest-observed date, and observation count per taxon.
- Deleting the last observation MUST remove the taxon from the derived life list. No separate observed boolean may be authoritative.

## Wishlist behavior

Add and remove are idempotent. Wishlist state is independent from observations and watches: observing a bird MUST NOT remove it, and adding/removing it MUST NOT change another state.

## Watch behavior

A watch requires one catalog taxon, an Arizona center selected through the existing validated location boundary, and radius from 1 through 300 miles. The stored center is per watch; there is no global home location. Creating or replacing a watch MUST NOT itself evaluate sightings or send email.

Pause retains the definition but prevents future match evaluation. Resume MUST revalidate current Arizona catalog identity and establishes a new activation boundary so pre-resume observations cannot trigger as new; a stale watch may still pause or delete safely but cannot resume. Replacing an active watch with a changed center or radius also establishes a new activation boundary; an identical replacement is idempotent, and editing a paused watch does not reactivate it.

Each watch MUST have an internal opaque stable watch ID and opaque activation generation. Creation establishes both; changed active replacement and resume create a new activation generation; identical replacement, pause, and paused edits preserve it. These fields are internal and MUST NOT enter collection API responses.

Pause and delete MUST transactionally persist a side-effect-free cancellation-request tombstone on the actual state transition so deleted-watch taxon identity is not lost. Dedupe uses stable watch ID, activation generation, and reason—not a wall-clock timestamp. The tombstone exposes only opaque dedupe identity, species code, reason, and request time—never center or credentials. It is not an event, outbox, or SMTP intent. The evaluator/calendar child consumes it and conditionally creates cancellation intent only when an accepted unexpired event exists; otherwise it resolves it without a side effect.

## API

Typed bounded endpoints MUST support:

- observation create/list/get/edit/delete;
- derived life-list list;
- wishlist list/add/remove;
- watches list/create-or-replace/pause/resume/delete;
- a combined per-species collection-state read for profile presentation.

Mutations MUST be serialized within the single local app, use explicit DuckDB transactions, and return safe busy/conflict/not-found errors. Browser code MUST never access DuckDB directly. Reads are network-free; collection mutations MUST NOT call eBird, weather, GLM, SMTP, or calendar delivery.

## Browser behavior

“My Birds” MUST provide accessible Life List, Observations, Wishlist, and Watches views. Forms use native labels, date input, validation, confirmation for hard deletion, and visible success/error states. Species selection MUST come from the local catalog. Species profiles MAY expose explicit add-observation, wishlist, and watch controls governed here; no implicit mutation is allowed.

No personal location, notes, origin, watch center, or recipient data may appear in logs, model prompts, traces, bundles, committed fixtures, or catalog/public evidence responses.

## Retention

Observations, wishlist, and watches persist until explicit user edit/delete. Hard-deleted observation content is not retained by this feature. Database backups are outside the application deletion guarantee and MUST be described as an operational limit if backups are later introduced.

## Acceptance scenarios

- Two observations for one species yield one life-list taxon with count two and correct first/latest dates.
- Editing one event updates derived dates/counts; deleting the last event removes membership.
- Wishlist remains after observation creation and watch removal.
- A hybrid can be observed, wished, and watched without parent inference.
- Pause/resume changes activation boundaries without evaluating or delivering an alert during the request.
- Invalid/stale species, invalid date, non-Arizona watch center, radius outside 1–300, busy database, and missing IDs return safe explicit states.
- API and UI expose no credential, raw arbitrary payload, or personal data outside the requested local surface.

## Explicit exclusions

No eBird life-list import, attachments, photo/audio binaries, multi-user ownership, remote sync, automatic geocoding of free-text observation locations, social sharing, target planning, match evaluation, or SMTP delivery.
