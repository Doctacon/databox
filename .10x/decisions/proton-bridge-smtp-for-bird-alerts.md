Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Use generic SMTP through Proton Mail Bridge for bird alerts

## Context

Watched-bird alerts require a standards-compatible SMTP transport for iCalendar invitations. Direct Google Calendar OAuth and direct Gmail SMTP were considered but would increase proprietary integration and credential scope. The user already operates Proton Mail Bridge locally.

Proton Mail Bridge exposes local IMAP/SMTP services on loopback, supports STARTTLS or SSL with a per-install self-signed certificate, and is open source under GPL-3.0. Bridge must be running for the local SMTP endpoint to work.

## Decision

1. Databox will implement provider-neutral SMTP and configure the initial local deployment through Proton Mail Bridge.
2. The SMTP host MUST be loopback and MUST use the actual Bridge SMTP port from local configuration.
3. STARTTLS is the selected connection mode.
4. TLS verification MUST trust the exact exported Bridge public certificate through a configured CA-file path. Databox MUST NOT disable certificate or hostname verification and MUST NOT use the exported private key.
5. Authentication MUST use Bridge-generated credentials, not the user's Proton account password.
6. The authenticated Proton address will be the calendar organizer/sender; the configured Gmail destination will be the attendee/recipient.
7. Bridge startup is an operational prerequisite for scheduled alert delivery.
8. Host, port, username, password, CA path, sender, recipient, and display-name values remain local environment configuration. Values MUST NOT be recorded in `.10x`, committed files, browser assets, logs, traces, persisted report payloads, or test snapshots.
9. The user authorized one bounded live SMTP test message and one bounded live iCalendar invitation during the alert-delivery verification step. Ambiguous delivery outcomes MUST NOT be automatically retried as new messages.

## Alternatives considered

- **Direct Gmail SMTP with an app password:** viable but rejected because Bridge is already available and avoids Google sender authentication.
- **Google Calendar API/OAuth:** rejected by the existing watched-alert policy in favor of open iCalendar/SMTP.
- **Disable TLS verification for localhost:** rejected; the exact exported Bridge certificate provides a safe trust anchor.
- **Use the exported Bridge private key:** rejected; an SMTP client needs only the public certificate as a trust anchor.
- **Hard-code Proton Bridge:** rejected; transport remains generic SMTP so the provider can change through local configuration.

## Consequences

- Bridge resets/reinstalls may rotate its generated password or TLS certificate and require local environment updates.
- SMTP acceptance means accepted by Bridge, not confirmed Gmail inbox or calendar delivery; durable outbox and delivery-unknown semantics remain necessary.
- Verification must redact configuration and assert that no secret or personal address reaches logs, traces, browser bundles, committed files, or durable evidence.
