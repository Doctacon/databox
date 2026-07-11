"""Explicit generic-SMTP delivery for persisted bird-alert outbox rows."""

from __future__ import annotations

import ipaddress
import re
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Literal, Protocol

import duckdb
from pydantic import BaseModel, ConfigDict, SecretStr, model_validator

from databox.bird_alert_outbox import (
    ALERT_SCHEMA,
    CalendarPayload,
    build_calendar_mime,
    claim_next_outbox,
    record_attempt_outcome,
    record_pre_send_outcome,
    start_send_attempt,
)

RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15))


@dataclass(frozen=True, repr=False)
class SmtpRuntimeConfig:
    host: str
    port: int
    username: str
    password: str
    organizer: str
    recipient: str
    ca_file: Path


class BirdAlertSmtpSettings(BaseModel):
    """All SMTP values remain SecretStr and are revealed only to the transport."""

    model_config = ConfigDict(extra="forbid")

    enabled: SecretStr
    security: SecretStr
    host: SecretStr
    port: SecretStr
    username: SecretStr
    password: SecretStr
    organizer: SecretStr
    recipient: SecretStr
    ca_file: SecretStr

    @model_validator(mode="after")
    def validate_boundary(self) -> BirdAlertSmtpSettings:
        values = {
            name: getattr(self, name).get_secret_value()
            for name in (
                "enabled",
                "security",
                "host",
                "port",
                "username",
                "password",
                "organizer",
                "recipient",
                "ca_file",
            )
        }
        if any(not value or value != value.strip() for value in values.values()):
            raise ValueError("alert SMTP configuration is incomplete")
        if values["enabled"].lower() not in {"true", "1", "yes"}:
            raise ValueError("alert SMTP delivery is not enabled")
        if values["security"].lower() != "starttls":
            raise ValueError("alert SMTP security must be STARTTLS")
        try:
            address = ipaddress.ip_address(values["host"])
        except ValueError:
            raise ValueError("alert SMTP host must be numeric loopback") from None
        if str(address) not in {"127.0.0.1", "::1"}:
            raise ValueError("alert SMTP host must be numeric loopback")
        try:
            port = int(values["port"])
        except ValueError:
            raise ValueError("alert SMTP port is invalid") from None
        if str(port) != values["port"] or not 1 <= port <= 65535:
            raise ValueError("alert SMTP port is invalid")
        if values["organizer"] != values["username"]:
            raise ValueError("alert organizer must match authenticated username")
        address_pattern = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9.-]{1,190}")
        for name in ("username", "organizer", "recipient"):
            if address_pattern.fullmatch(values[name]) is None:
                raise ValueError("alert SMTP address is invalid")
        certificate = Path(values["ca_file"])
        if not certificate.is_file():
            raise ValueError("alert SMTP certificate is unavailable")
        try:
            pem = certificate.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise ValueError("alert SMTP certificate is unavailable") from None
        if (
            pem.count("-----BEGIN CERTIFICATE-----") != 1
            or pem.count("-----END CERTIFICATE-----") != 1
            or "PRIVATE KEY" in pem
        ):
            raise ValueError("alert SMTP certificate must contain one public certificate")
        return self

    def runtime(self) -> SmtpRuntimeConfig:
        return SmtpRuntimeConfig(
            host=self.host.get_secret_value(),
            port=int(self.port.get_secret_value()),
            username=self.username.get_secret_value(),
            password=self.password.get_secret_value(),
            organizer=self.organizer.get_secret_value(),
            recipient=self.recipient.get_secret_value(),
            ca_file=Path(self.ca_file.get_secret_value()),
        )


class SmtpConnection(Protocol):
    def ehlo(self) -> Any: ...
    def starttls(self, *, context: ssl.SSLContext) -> Any: ...
    def login(self, user: str, password: str) -> Any: ...
    def send_message(self, message: EmailMessage) -> Any: ...
    def quit(self) -> Any: ...
    def close(self) -> Any: ...


SmtpFactory = Callable[..., SmtpConnection]


@dataclass(frozen=True)
class DeliveryResult:
    status: Literal["idle", "accepted", "retry_wait", "failed", "delivery_unknown"]
    outbox_id: str | None
    safe_reason: str | None
    next_attempt_at: str | None = None


def _tls_context(ca_file: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(ca_file))
    return context


def _response_class(exc: BaseException) -> Literal["transient", "permanent"] | None:
    if isinstance(exc, smtplib.SMTPResponseException):
        return "transient" if 400 <= int(exc.smtp_code) < 500 else "permanent"
    if isinstance(
        exc,
        smtplib.SMTPAuthenticationError
        | smtplib.SMTPRecipientsRefused
        | smtplib.SMTPNotSupportedError,
    ):
        return "permanent"
    return None


def _prepare(config: SmtpRuntimeConfig, factory: SmtpFactory) -> SmtpConnection:
    client = factory(config.host, config.port, timeout=20)
    try:
        client.ehlo()
        client.starttls(context=_tls_context(config.ca_file))
        client.ehlo()
        client.login(config.username, config.password)
        return client
    except Exception:
        try:
            client.close()
        except Exception:
            pass
        raise


def _close(client: SmtpConnection) -> None:
    try:
        client.quit()
    except Exception:
        try:
            client.close()
        except Exception:
            pass


def _retry_or_fail(
    connection: duckdb.DuckDBPyConnection,
    *,
    outbox_id: str,
    claim_token: str,
    prior_attempts: int,
    now: datetime,
    reason: str,
    after_send_started: bool,
) -> DeliveryResult:
    attempt_number = prior_attempts + 1
    if attempt_number <= len(RETRY_DELAYS):
        next_at = now + RETRY_DELAYS[attempt_number - 1]
        recorder = record_attempt_outcome if after_send_started else record_pre_send_outcome
        recorder(
            connection,
            outbox_id=outbox_id,
            claim_token=claim_token,
            outcome="retry_wait",
            now=now,
            next_attempt_at=next_at,
            safe_reason=reason,
        )
        return DeliveryResult("retry_wait", outbox_id, reason, next_at.astimezone(UTC).isoformat())
    recorder = record_attempt_outcome if after_send_started else record_pre_send_outcome
    recorder(
        connection,
        outbox_id=outbox_id,
        claim_token=claim_token,
        outcome="failed",
        now=now,
        safe_reason=reason,
    )
    return DeliveryResult("failed", outbox_id, reason)


def deliver_next_outbox(
    connection: duckdb.DuckDBPyConnection,
    *,
    settings: BirdAlertSmtpSettings,
    now: datetime,
    smtp_factory: SmtpFactory = smtplib.SMTP,
) -> DeliveryResult:
    """Deliver at most one row. Calling this function is the explicit send trigger."""

    config = settings.runtime()
    claim = claim_next_outbox(connection, now=now)
    if claim is None:
        return DeliveryResult("idle", None, None)
    try:
        client = _prepare(config, smtp_factory)
    except Exception as exc:
        classification = _response_class(exc)
        if classification == "permanent" or isinstance(exc, ssl.SSLError | ValueError):
            record_pre_send_outcome(
                connection,
                outbox_id=claim.outbox_id,
                claim_token=claim.claim_token,
                outcome="failed",
                now=now,
                safe_reason="smtp_configuration_or_auth_rejected",
            )
            return DeliveryResult("failed", claim.outbox_id, "smtp_configuration_or_auth_rejected")
        return _retry_or_fail(
            connection,
            outbox_id=claim.outbox_id,
            claim_token=claim.claim_token,
            prior_attempts=claim.attempt_count,
            now=now,
            reason="smtp_pre_acceptance_transient",
            after_send_started=False,
        )

    message = build_calendar_mime(
        claim.payload,
        organizer=config.organizer,
        attendee=config.recipient,
    )
    start_send_attempt(
        connection,
        outbox_id=claim.outbox_id,
        claim_token=claim.claim_token,
        now=now,
    )
    try:
        refused = client.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    except Exception as exc:
        _close(client)
        classification = _response_class(exc)
        if classification == "transient":
            return _retry_or_fail(
                connection,
                outbox_id=claim.outbox_id,
                claim_token=claim.claim_token,
                prior_attempts=claim.attempt_count,
                now=now,
                reason="smtp_explicit_transient_rejection",
                after_send_started=True,
            )
        if classification == "permanent":
            record_attempt_outcome(
                connection,
                outbox_id=claim.outbox_id,
                claim_token=claim.claim_token,
                outcome="failed",
                now=now,
                safe_reason="smtp_explicit_permanent_rejection",
            )
            return DeliveryResult("failed", claim.outbox_id, "smtp_explicit_permanent_rejection")
        # Once DATA transmission may have begun, disconnect/timeout/unknown errors are ambiguous.
        record_attempt_outcome(
            connection,
            outbox_id=claim.outbox_id,
            claim_token=claim.claim_token,
            outcome="delivery_unknown",
            now=now,
            safe_reason="smtp_acceptance_ambiguous",
        )
        return DeliveryResult("delivery_unknown", claim.outbox_id, "smtp_acceptance_ambiguous")
    _close(client)
    record_attempt_outcome(
        connection,
        outbox_id=claim.outbox_id,
        claim_token=claim.claim_token,
        outcome="accepted",
        now=now,
        safe_reason="smtp_bridge_accepted",
    )
    return DeliveryResult("accepted", claim.outbox_id, "smtp_bridge_accepted")


def preflight_smtp(
    settings: BirdAlertSmtpSettings,
    *,
    smtp_factory: SmtpFactory = smtplib.SMTP,
) -> None:
    """Explicitly validate TLS, hostname, and authentication without sending."""

    client = _prepare(settings.runtime(), smtp_factory)
    _close(client)


def send_bounded_live_verification(
    connection: duckdb.DuckDBPyConnection,
    *,
    settings: BirdAlertSmtpSettings,
    kind: Literal["test_email", "test_invitation"],
    now: datetime,
    smtp_factory: SmtpFactory = smtplib.SMTP,
) -> Literal["accepted", "failed", "delivery_unknown"]:
    """Send each authorized verification kind at most once, including ambiguous attempts."""

    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {ALERT_SCHEMA}")
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {ALERT_SCHEMA}.smtp_verification (
          kind VARCHAR PRIMARY KEY, state VARCHAR NOT NULL, attempted_at VARCHAR NOT NULL,
          resolved_at VARCHAR, safe_reason VARCHAR,
          CHECK (kind IN ('test_email','test_invitation')),
          CHECK (state IN ('started','accepted','failed','delivery_unknown'))
        )"""
    )
    timestamp = now.astimezone(UTC).isoformat()
    connection.execute("BEGIN TRANSACTION")
    try:
        existing = connection.execute(
            f"SELECT count(*) FROM {ALERT_SCHEMA}.smtp_verification WHERE kind=?", [kind]
        ).fetchone()
        if existing is None or int(existing[0]) > 0:
            raise ValueError("this SMTP verification was already attempted")
        connection.execute(
            f"INSERT INTO {ALERT_SCHEMA}.smtp_verification VALUES (?, 'started', ?, NULL, NULL)",
            [kind, timestamp],
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise

    config = settings.runtime()
    try:
        client = _prepare(config, smtp_factory)
    except Exception:
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.smtp_verification SET state='failed', resolved_at=?,
                safe_reason='smtp_preflight_failed' WHERE kind=?""",
            [timestamp, kind],
        )
        return "failed"
    if kind == "test_email":
        message = EmailMessage()
        message["From"] = config.organizer
        message["To"] = config.recipient
        message["Subject"] = "Rufous SMTP verification"
        message.set_content(
            "This is the single authorized Rufous SMTP transport verification message."
        )
    else:
        start = now.astimezone(UTC) + timedelta(days=1)
        payload = CalendarPayload(
            species_code="verification",
            common_name="Rufous verification bird",
            scientific_name=None,
            event_uid="databox-smtp-verification@local",
            sequence=0,
            method="REQUEST",
            dtstamp=timestamp,
            morning_start=start.isoformat(),
            morning_end=(start + timedelta(hours=2)).isoformat(),
            event_horizon_end=(now.astimezone(UTC) + timedelta(days=5)).isoformat(),
            location_id="verification",
            location_name="Rufous SMTP verification",
            latitude=0,
            longitude=0,
            confirmed_distance_miles=0,
            independent_submission_count=1,
            newest_observation_at=timestamp,
        )
        message = build_calendar_mime(
            payload, organizer=config.organizer, attendee=config.recipient
        )
    try:
        refused = client.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    except Exception as exc:
        _close(client)
        classification = _response_class(exc)
        if classification is not None:
            connection.execute(
                f"""UPDATE {ALERT_SCHEMA}.smtp_verification SET state='failed',
                    resolved_at=?, safe_reason='smtp_explicit_rejection' WHERE kind=?""",
                [timestamp, kind],
            )
            return "failed"
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.smtp_verification SET state='delivery_unknown',
                resolved_at=?, safe_reason='smtp_acceptance_ambiguous' WHERE kind=?""",
            [timestamp, kind],
        )
        return "delivery_unknown"
    _close(client)
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.smtp_verification SET state='accepted', resolved_at=?,
            safe_reason='smtp_bridge_accepted' WHERE kind=?""",
        [timestamp, kind],
    )
    return "accepted"


def settings_from_global(global_settings: Any) -> BirdAlertSmtpSettings:
    """Build validated SMTP settings without exposing any value in errors or repr."""

    return BirdAlertSmtpSettings(
        enabled=global_settings.alert_smtp_enabled,
        security=global_settings.alert_smtp_security,
        host=global_settings.alert_smtp_host,
        port=global_settings.alert_smtp_port,
        username=global_settings.alert_smtp_username,
        password=global_settings.alert_smtp_password,
        organizer=global_settings.alert_smtp_organizer,
        recipient=global_settings.alert_smtp_recipient,
        ca_file=global_settings.alert_smtp_ca_file,
    )
