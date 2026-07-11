"""Trip-plan calendar identity, canonical payload, durable outbox, and SMTP delivery.

Trip rows deliberately live in separate relationship-constrained tables from watched-bird
rows.  Nothing in this module runs at import, startup, plan creation, or GET time.
"""

from __future__ import annotations

import hashlib
import json
import re
import smtplib
import ssl
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.policy import SMTP
from html import unescape
from typing import Literal
from urllib.parse import unquote

import duckdb
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from databox.bird_alert_delivery import (
    RETRY_DELAYS,
    BirdAlertSmtpSettings,
    DeliveryResult,
    SmtpFactory,
    _close,
    _prepare,
    _response_class,
)

TRIP_SCHEMA = "birding_calendar"
MAX_PAYLOAD_BYTES = 32_768
CLAIM_TTL = timedelta(minutes=5)
RESOLVED_RETENTION = timedelta(days=90)

_EMAIL_DOMAIN = (
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\."
    r")+[A-Za-z]{2,63}|localhost|"
    r"\[(?:IPv6:)?[0-9A-Fa-f:.]{2,45}\]"
)
_EMAIL_MARKER = re.compile(
    r"(?<![\w.!#$%&'*+/=?^`{|}~-])"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@"
    rf"(?:{_EMAIL_DOMAIN})(?![\w.-])",
    re.IGNORECASE,
)
_DOMAIN_NAME = r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"
_DOMAIN_URL_MARKER = re.compile(
    rf"(?<![A-Za-z0-9.-])(?:www\.{_DOMAIN_NAME}(?::\d{{1,5}})?"
    rf"(?:/[^\s]*|\?[^\s]*)?|{_DOMAIN_NAME}(?::\d{{1,5}}|/[^\s]*|\?[^\s]*))"
    r"(?![A-Za-z0-9.-])",
    re.IGNORECASE,
)
_URL_MARKERS = (
    re.compile(r"(?<![A-Za-z])h\s*t\s*t\s*p\s*s?://", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]{0,31}://\S+"),
)
_LABEL_QUALIFIER = r"(?:\s*\([^()\r\n]{1,40}\))?"
_LABEL_CONNECTOR = r"\s*(?:-|:|=|/|;|\bis\b)\s*"
_CREDENTIAL_ASSIGNMENT = re.compile(
    rf"(?<![\w-])([A-Za-z][A-Za-z0-9_-]{{0,127}}){_LABEL_QUALIFIER}"
    rf"{_LABEL_CONNECTOR}\S+",
    re.IGNORECASE,
)
_SECRET_MARKER = re.compile(
    rf"\b(?:(?:api[\s_-]*key|access[\s_-]*token|auth(?:orization)?[\s_-]*token|"
    rf"credential(?:s)?|password|private[\s_-]*key|secret|token)\b"
    rf"{_LABEL_QUALIFIER}{_LABEL_CONNECTOR}\S+|"
    rf"key\b{_LABEL_QUALIFIER}\s*[-:=]\s*\S+)",
    re.IGNORECASE,
)
_RECIPIENT_MARKER = re.compile(
    rf"\b(?:recipient|attendee|organizer)\b{_LABEL_QUALIFIER}{_LABEL_CONNECTOR}\S+",
    re.IGNORECASE,
)
_PRIVATE_KEY_MARKER = re.compile(r"-----\s*BEGIN\s+(?:[A-Z]+\s+)?PRIVATE\s+KEY\s*-----", re.I)
_BEARER_TOKEN_MARKER = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_COORDINATE_PAIR = re.compile(
    r"(?<![\d.])([+-]?(?:\d{1,3}(?:\.\d+)?|\.\d+))\s*°?\s*([NS])?(?![A-Za-z])"
    r"\s*([,;/]|\band\b)\s*"
    r"([+-]?(?:\d{1,3}(?:\.\d+)?|\.\d+))\s*°?\s*([EW])?(?![A-Za-z])"
    r"(?![\d.])",
    re.IGNORECASE,
)
_MAX_CARDINAL_CONNECTOR_CHARS = 48
_COORDINATE_CARDINAL_PAIR = re.compile(
    r"(?<![\d.])([+-]?(?:\d{1,3}(?:\.\d+)?|\.\d+))\s*°?\s*([NS])(?![A-Za-z])"
    rf"([\s\S]{{1,{_MAX_CARDINAL_CONNECTOR_CHARS}}}?)"
    r"([+-]?(?:\d{1,3}(?:\.\d+)?|\.\d+))\s*°?\s*([EW])(?![A-Za-z])"
    r"(?![\d.])",
    re.IGNORECASE,
)
_MAX_COORDINATE_CONNECTOR_CHARS = 48
_COORDINATE_LABEL = re.compile(
    r"\b(?:coordinates?|gps|lat(?:itude)?\s*(?:[-/&,]|\band\b)\s*"
    r"(?:lon|long|longitude))\b",
    re.IGNORECASE,
)
_WGS84_LABEL = re.compile(r"\(\s*WGS\s*84\s*\)", re.IGNORECASE)


class UnsafeTripCalendarContentError(ValueError):
    """Persisted prose contains content prohibited from calendar descriptions."""


def _normalize_privacy_unicode(value: str) -> str:
    degree_variants = str.maketrans({"º": "°", "˚": "°", "⁰": "°", "∘": "°"})
    return unicodedata.normalize("NFKC", value.translate(degree_variants))


def _decoded_privacy_text(value: str) -> str:
    """Build a canonical detection-only view without changing persisted prose."""

    decoded = _normalize_privacy_unicode(value)
    for _ in range(2):
        expanded = _normalize_privacy_unicode(unescape(unquote(decoded)))
        if expanded == decoded:
            break
        decoded = expanded
    decoded = "".join(
        "-"
        if unicodedata.category(character) == "Pd"
        else "."
        if character in {"\u3002", "\uff0e", "\uff61"}
        else character
        for character in decoded
    )
    return re.sub(r"\s*([./:@\[\]])\s*", r"\1", decoded)


def _is_credential_identifier(identifier: str) -> bool:
    compact = identifier.lower().replace("_", "").replace("-", "")
    if any(marker in compact for marker in ("secret", "password", "passwd", "token", "credential")):
        return True
    return any(marker in compact for marker in ("api", "private", "access", "auth")) and any(
        material in compact
        for material in ("key", "client", "credential", "secret", "token", "password")
    )


def _validate_calendar_description_text(value: str) -> str:
    decoded = _decoded_privacy_text(value)
    credential_assignment = any(
        _is_credential_identifier(match.group(1))
        for match in _CREDENTIAL_ASSIGNMENT.finditer(decoded)
    )
    domain_url = _DOMAIN_URL_MARKER.search(decoded)
    if (
        _EMAIL_MARKER.search(decoded)
        or any(marker.search(decoded) for marker in _URL_MARKERS)
        or domain_url
        or credential_assignment
        or _SECRET_MARKER.search(decoded)
        or _RECIPIENT_MARKER.search(decoded)
        or _PRIVATE_KEY_MARKER.search(decoded)
        or _BEARER_TOKEN_MARKER.search(decoded)
    ):
        raise UnsafeTripCalendarContentError("trip calendar description contains prohibited data")
    coordinate_matches = (
        *_COORDINATE_PAIR.finditer(decoded),
        *_COORDINATE_CARDINAL_PAIR.finditer(decoded),
    )
    for match in coordinate_matches:
        latitude, north_south, _separator, longitude, east_west = match.groups()
        if (
            float(latitude) > 90
            or float(latitude) < -90
            or float(longitude) > 180
            or float(longitude) < -180
        ):
            continue
        fractions = [part.partition(".")[2] for part in (latitude, longitude)]
        preceding_text = decoded[: match.start()]
        labels = list(_COORDINATE_LABEL.finditer(preceding_text))
        labeled_pair = False
        if labels:
            connector = preceding_text[labels[-1].end() :]
            connector_without_datum = _WGS84_LABEL.sub("", connector)
            labeled_pair = (
                len(connector) <= _MAX_COORDINATE_CONNECTOR_CHARS
                and not any(terminator in connector for terminator in ";.!?")
                and not any(character.isdigit() for character in connector_without_datum)
            )
        coordinate_shaped = (
            bool(north_south or east_west)
            or latitude.startswith(("+", "-"))
            or longitude.startswith(("+", "-"))
            or all(len(fraction) >= 3 for fraction in fractions)
            or labeled_pair
        )
        if coordinate_shaped:
            raise UnsafeTripCalendarContentError(
                "trip calendar description contains prohibited data"
            )
    return value


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return value.astimezone(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp is invalid") from None
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed


def _parse_arizona_time(value: str) -> datetime:
    parsed = _parse_time(value)
    if parsed.utcoffset() != timedelta(hours=-7):
        raise ValueError("Arizona trip timestamp must use the year-round -07:00 offset")
    return parsed


def _safe_text(value: str, name: str, maximum: int) -> str:
    if (
        not value
        or len(value) > maximum
        or "\r" in value
        or any(ord(char) < 32 and char not in "\n\t" for char in value)
    ):
        raise ValueError(f"{name} is invalid")
    return value


def _json_list(value: object, *, name: str, maximum: int = 50) -> list[str]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"{name} is malformed") from None
    if (
        not isinstance(parsed, list)
        or len(parsed) > maximum
        or any(not isinstance(item, str) or not item or len(item) > 1000 for item in parsed)
    ):
        raise ValueError(f"{name} is malformed")
    return parsed


class TripCalendarPayload(BaseModel):
    """Bounded canonical facts. Email configuration and private evidence are excluded."""

    model_config = ConfigDict(extra="forbid")

    event_kind: Literal["trip_plan"] = "trip_plan"
    trip_plan_id: str = Field(pattern=r"^trip_[A-Za-z0-9_-]{1,120}$")
    event_uid: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=0)
    method: Literal["REQUEST"] = "REQUEST"
    dtstamp: str = Field(max_length=64)
    window_start: str = Field(max_length=64)
    window_end: str = Field(max_length=64)
    location_name: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    field_plan_text: str = Field(min_length=1, max_length=6000)
    target_common_names: list[str] = Field(min_length=1, max_length=50)
    weather_status: str = Field(min_length=1, max_length=100)
    caveats: list[str] = Field(max_length=100)
    source_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("location_name", "field_plan_text", "weather_status")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        value = _safe_text(value, "calendar text", 6000)
        if info.field_name == "field_plan_text":
            _validate_calendar_description_text(value)
        return value

    @field_validator("target_common_names", "caveats")
    @classmethod
    def validate_lists(cls, value: list[str], info: ValidationInfo) -> list[str]:
        if any(not item or len(item) > 1000 or "\r" in item for item in value):
            raise ValueError("calendar list text is invalid")
        if info.field_name == "caveats":
            for item in value:
                _validate_calendar_description_text(item)
        return value

    @model_validator(mode="after")
    def validate_window(self) -> TripCalendarPayload:
        start = _parse_arizona_time(self.window_start)
        end = _parse_arizona_time(self.window_end)
        _parse_time(self.dtstamp)
        if end <= start or end - start > timedelta(days=1):
            raise ValueError("trip calendar window is invalid")
        return self

    def canonical_json(self) -> str:
        rendered = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        if len(rendered.encode()) > MAX_PAYLOAD_BYTES:
            raise ValueError("trip calendar payload exceeds its bound")
        return rendered

    @property
    def payload_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


@dataclass(frozen=True)
class TripClaim:
    outbox_id: str
    claim_token: str
    payload: TripCalendarPayload
    attempt_count: int


def ensure_trip_calendar_tables(connection: duckdb.DuckDBPyConnection) -> None:
    """Apply the additive runtime migration for the trip-only relationship union arm."""

    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {TRIP_SCHEMA}")
    connection.execute("CREATE SCHEMA IF NOT EXISTS birding_alerts")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS birding_alerts.runtime_settings (
             setting_key VARCHAR PRIMARY KEY, setting_value VARCHAR NOT NULL)"""
    )
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {TRIP_SCHEMA}.trip_event_intents (
          trip_plan_id VARCHAR PRIMARY KEY, event_kind VARCHAR NOT NULL,
          event_uid VARCHAR NOT NULL UNIQUE, sequence BIGINT NOT NULL,
          status VARCHAR NOT NULL, source_plan_hash VARCHAR NOT NULL,
          current_outbox_id VARCHAR, accepted_sequence BIGINT,
          created_at VARCHAR NOT NULL, updated_at VARCHAR NOT NULL,
          CHECK (event_kind='trip_plan'), CHECK (sequence >= 0),
          CHECK (accepted_sequence IS NULL OR accepted_sequence >= 0),
          CHECK (status IN ('pending','accepted','failed','delivery_unknown'))
        )"""
    )
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {TRIP_SCHEMA}.trip_outbox (
          outbox_id VARCHAR PRIMARY KEY, event_kind VARCHAR NOT NULL,
          trip_plan_id VARCHAR NOT NULL, event_uid VARCHAR NOT NULL,
          sequence BIGINT NOT NULL, method VARCHAR NOT NULL,
          payload_json VARCHAR NOT NULL, payload_hash VARCHAR NOT NULL,
          source_plan_hash VARCHAR NOT NULL, state VARCHAR NOT NULL,
          next_attempt_at VARCHAR NOT NULL, claim_token VARCHAR,
          claimed_at VARCHAR, claim_expires_at VARCHAR, send_started_at VARCHAR,
          attempt_count BIGINT NOT NULL, created_at VARCHAR NOT NULL,
          updated_at VARCHAR NOT NULL, terminal_at VARCHAR, safe_terminal_reason VARCHAR,
          UNIQUE(event_uid, sequence, method),
          CHECK (event_kind='trip_plan'), CHECK (method='REQUEST'),
          CHECK (attempt_count >= 0),
          CHECK (state IN ('pending','claimed','retry_wait','accepted','failed',
                           'delivery_unknown','superseded'))
        )"""
    )
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {TRIP_SCHEMA}.trip_outbox_attempts (
          attempt_id VARCHAR PRIMARY KEY, outbox_id VARCHAR NOT NULL,
          attempt_number BIGINT NOT NULL, claim_token VARCHAR NOT NULL,
          phase VARCHAR NOT NULL, safe_reason VARCHAR, occurred_at VARCHAR NOT NULL,
          CHECK (phase IN ('send_started','accepted','retry_wait','failed',
                           'delivery_unknown','claim_recovered'))
        )"""
    )
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {TRIP_SCHEMA}.trip_accepted_snapshots (
          event_uid VARCHAR PRIMARY KEY, trip_plan_id VARCHAR NOT NULL,
          accepted_sequence BIGINT NOT NULL, payload_json VARCHAR NOT NULL,
          payload_hash VARCHAR NOT NULL, accepted_at VARCHAR NOT NULL
        )"""
    )
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {TRIP_SCHEMA}.trip_outbox_dedupe (
          outbox_id VARCHAR PRIMARY KEY, event_uid VARCHAR NOT NULL,
          sequence BIGINT NOT NULL, payload_hash VARCHAR NOT NULL,
          terminal_at VARCHAR NOT NULL, UNIQUE(event_uid, sequence)
        )"""
    )


def validate_trip_calendar_integrity(connection: duckdb.DuckDBPyConnection) -> None:
    """Fail closed on relationship corruption DuckDB cannot constrain with mutable FKs."""

    violations = connection.execute(
        f"""SELECT
          (SELECT count(*) FROM {TRIP_SCHEMA}.trip_event_intents AS intent
             LEFT JOIN birding_agent.trip_plans AS plan
               ON plan.trip_plan_id=intent.trip_plan_id
             WHERE plan.trip_plan_id IS NULL)
          + (SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox AS outbox
             LEFT JOIN {TRIP_SCHEMA}.trip_event_intents AS intent
               ON intent.trip_plan_id=outbox.trip_plan_id AND intent.event_uid=outbox.event_uid
             WHERE intent.trip_plan_id IS NULL OR outbox.event_kind <> 'trip_plan')
          + (SELECT count(*) FROM {TRIP_SCHEMA}.trip_event_intents AS intent
             LEFT JOIN {TRIP_SCHEMA}.trip_outbox AS outbox
               ON outbox.outbox_id=intent.current_outbox_id
              AND outbox.trip_plan_id=intent.trip_plan_id
              AND outbox.event_uid=intent.event_uid
              AND outbox.sequence=intent.sequence
              AND outbox.source_plan_hash=intent.source_plan_hash
             WHERE intent.current_outbox_id IS NULL OR outbox.outbox_id IS NULL
                OR intent.event_kind <> 'trip_plan')
          + (SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox_attempts AS attempt
             LEFT JOIN {TRIP_SCHEMA}.trip_outbox AS outbox
               ON outbox.outbox_id=attempt.outbox_id WHERE outbox.outbox_id IS NULL)
          + (SELECT count(*) FROM {TRIP_SCHEMA}.trip_accepted_snapshots AS snapshot
             LEFT JOIN {TRIP_SCHEMA}.trip_event_intents AS intent
               ON intent.event_uid=snapshot.event_uid
              AND intent.trip_plan_id=snapshot.trip_plan_id
             WHERE intent.event_uid IS NULL OR intent.accepted_sequence IS NULL
                OR snapshot.accepted_sequence > intent.accepted_sequence)
        """
    ).fetchone()
    if violations is None or int(violations[0]) != 0:
        raise ValueError("trip calendar relationship integrity check failed")


def _installation_id(connection: duckdb.DuckDBPyConnection) -> str:
    row = connection.execute(
        """SELECT setting_value FROM birding_alerts.runtime_settings
           WHERE setting_key='installation_id'"""
    ).fetchone()
    if row is not None:
        return str(row[0])
    value = str(uuid.uuid4())
    connection.execute(
        "INSERT INTO birding_alerts.runtime_settings VALUES ('installation_id', ?)", [value]
    )
    return value


def trip_event_uid(installation_id: str, trip_plan_id: str) -> str:
    digest = hashlib.sha256(f"{installation_id}|trip_plan|{trip_plan_id}".encode()).hexdigest()
    return f"rufous-trip-{digest}@local"


def _canonical_source(connection: duckdb.DuckDBPyConnection, plan_id: str) -> dict[str, object]:
    plans = connection.execute(
        """SELECT trip_plan_id, normalized_location_name, latitude, longitude, region_code,
                  window_start, window_end, plan_status, field_plan_text, caveats_json
           FROM birding_agent.trip_plans WHERE trip_plan_id=? LIMIT 2""",
        [plan_id],
    ).fetchall()
    if len(plans) != 1:
        raise ValueError("trip plan is unavailable or non-unique")
    plan = plans[0]
    if (
        str(plan[0]) != plan_id
        or str(plan[4]) != "US-AZ"
        or str(plan[7]) != "complete"
        or any(plan[index] is None for index in (1, 2, 3, 5, 6, 8))
    ):
        raise ValueError("trip plan is incomplete")
    location = _safe_text(str(plan[1]), "normalized location", 300)
    field_plan = _safe_text(str(plan[8]), "field plan", 6000)
    start, end = _parse_arizona_time(str(plan[5])), _parse_arizona_time(str(plan[6]))
    if end <= start or end - start > timedelta(days=1):
        raise ValueError("trip plan window is invalid")
    plan_caveats = _json_list(plan[9], name="trip plan caveats")

    recommendations = connection.execute(
        """SELECT recommendation_id, common_name, recommendation_group, rank_order,
                  caveats_json FROM birding_agent.trip_plan_recommendations
           WHERE trip_plan_id=? ORDER BY recommendation_group, rank_order, recommendation_id""",
        [plan_id],
    ).fetchall()
    if not recommendations:
        raise ValueError("trip plan recommendations are unavailable")
    names: list[str] = []
    recommendation_facts: list[object] = []
    caveats = list(plan_caveats)
    for rec in recommendations:
        if rec[0] is None or rec[1] is None or rec[2] is None or rec[3] is None:
            raise ValueError("trip plan recommendation is incomplete")
        name = _safe_text(str(rec[1]), "target common name", 200)
        names.append(name)
        rec_caveats = _json_list(rec[4], name="recommendation caveats")
        caveats.extend(rec_caveats)
        recommendation_facts.append([str(rec[0]), name, str(rec[2]), int(rec[3]), rec_caveats])

    evidence = connection.execute(
        """SELECT evidence_id, recommendation_id, source, evidence_type, status,
                  summary_json, caveats_json, source_record_id
           FROM birding_agent.trip_plan_evidence
           WHERE trip_plan_id=? ORDER BY source, evidence_type, evidence_id""",
        [plan_id],
    ).fetchall()
    ebird = [
        row for row in evidence if str(row[2]) == "ebird" and str(row[3]) == "recent_observation"
    ]
    for row in ebird:
        source_id = row[7]
        if source_id is None or not str(source_id).strip():
            raise ValueError("trip plan evidence source identity is unavailable")
        authority = connection.execute(
            """SELECT count(*),
                      count(*) FILTER (
                        WHERE is_valid IS TRUE AND is_reviewed IS TRUE
                          AND is_location_private IS FALSE)
               FROM environmental_observations.fact_bird_observation
               WHERE source_observation_id=?""",
            [str(source_id)],
        ).fetchone()
        if authority is None or authority != (1, 1):
            raise ValueError("trip plan evidence source is ineligible")
    weather = [row for row in evidence if str(row[2]) == "open_meteo"]
    if len(weather) != 1 or weather[0][4] is None:
        raise ValueError("trip plan weather status is unavailable")
    weather_status = _safe_text(str(weather[0][4]), "weather status", 100)
    evidence_facts: list[object] = []
    for row in evidence:
        row_caveats = _json_list(row[6], name="evidence caveats")
        caveats.extend(row_caveats)
        try:
            summary = json.loads(str(row[5]))
        except (TypeError, ValueError):
            raise ValueError("trip plan evidence is malformed") from None
        evidence_facts.append(
            [row[0], row[1], row[2], row[3], row[4], summary, row_caveats, row[7]]
        )
    if len(caveats) > 100:
        raise ValueError("trip plan caveats exceed their bound")
    _validate_calendar_description_text(field_plan)
    for caveat in caveats:
        _validate_calendar_description_text(caveat)
    facts: dict[str, object] = {
        "trip_plan_id": plan_id,
        "location_name": location,
        "latitude": float(plan[2]),
        "longitude": float(plan[3]),
        "window_start": str(plan[5]),
        "window_end": str(plan[6]),
        "field_plan_text": field_plan,
        "target_common_names": names,
        "weather_status": weather_status,
        "caveats": caveats,
        "recommendations": recommendation_facts,
        "evidence": evidence_facts,
    }
    source_json = json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    facts["source_plan_hash"] = hashlib.sha256(source_json.encode()).hexdigest()
    return facts


def canonical_trip_payload(
    connection: duckdb.DuckDBPyConnection,
    plan_id: str,
    *,
    event_uid: str,
    sequence: int,
    now: datetime,
) -> TripCalendarPayload:
    facts = _canonical_source(connection, plan_id)
    return TripCalendarPayload(
        trip_plan_id=plan_id,
        event_uid=event_uid,
        sequence=sequence,
        dtstamp=_iso(now),
        window_start=facts["window_start"],
        window_end=facts["window_end"],
        location_name=facts["location_name"],
        latitude=facts["latitude"],
        longitude=facts["longitude"],
        field_plan_text=facts["field_plan_text"],
        target_common_names=facts["target_common_names"],
        weather_status=facts["weather_status"],
        caveats=facts["caveats"],
        source_plan_hash=facts["source_plan_hash"],
    )


def _outbox_id(uid: str, sequence: int) -> str:
    return "trip_outbox_" + hashlib.sha256(f"{uid}|{sequence}|REQUEST".encode()).hexdigest()


def _enqueue_trip_invite_in_transaction(
    connection: duckdb.DuckDBPyConnection, plan_id: str, *, now: datetime
) -> str:
    existing = connection.execute(
        f"""SELECT event_uid, sequence, status, source_plan_hash, current_outbox_id
            FROM {TRIP_SCHEMA}.trip_event_intents WHERE trip_plan_id=?""",
        [plan_id],
    ).fetchone()
    if existing is not None and str(existing[2]) in {"pending", "delivery_unknown"}:
        if str(_canonical_source(connection, plan_id)["source_plan_hash"]) != str(existing[3]):
            raise ValueError("trip plan changed after invite creation")
        return str(existing[4])
    # Validate persisted description inputs before creating installation/event/outbox state.
    _canonical_source(connection, plan_id)
    uid = str(existing[0]) if existing else trip_event_uid(_installation_id(connection), plan_id)
    sequence = int(existing[1]) + 1 if existing else 0
    payload = canonical_trip_payload(connection, plan_id, event_uid=uid, sequence=sequence, now=now)
    outbox_id = _outbox_id(uid, sequence)
    timestamp = _iso(now)
    conflict = connection.execute(
        f"""SELECT payload_hash FROM {TRIP_SCHEMA}.trip_outbox WHERE outbox_id=?
            UNION ALL SELECT payload_hash FROM {TRIP_SCHEMA}.trip_outbox_dedupe
            WHERE outbox_id=?""",
        [outbox_id, outbox_id],
    ).fetchall()
    if conflict and any(str(row[0]) != payload.payload_hash for row in conflict):
        raise ValueError("trip invite identity conflicts with different canonical facts")
    if existing:
        connection.execute(
            f"""UPDATE {TRIP_SCHEMA}.trip_event_intents SET sequence=?, status='pending',
                source_plan_hash=?, current_outbox_id=?, updated_at=? WHERE trip_plan_id=?""",
            [sequence, payload.source_plan_hash, outbox_id, timestamp, plan_id],
        )
    else:
        connection.execute(
            f"""INSERT INTO {TRIP_SCHEMA}.trip_event_intents VALUES
                (?, 'trip_plan', ?, ?, 'pending', ?, ?, NULL, ?, ?)""",
            [plan_id, uid, sequence, payload.source_plan_hash, outbox_id, timestamp, timestamp],
        )
    if not conflict:
        connection.execute(
            f"""INSERT INTO {TRIP_SCHEMA}.trip_outbox VALUES
            (?, 'trip_plan', ?, ?, ?, 'REQUEST', ?, ?, ?, 'pending', ?,
             NULL, NULL, NULL, NULL, 0, ?, ?, NULL, NULL)""",
            [
                outbox_id,
                plan_id,
                uid,
                sequence,
                payload.canonical_json(),
                payload.payload_hash,
                payload.source_plan_hash,
                timestamp,
                timestamp,
                timestamp,
            ],
        )
    return outbox_id


def enqueue_trip_invite(
    connection: duckdb.DuckDBPyConnection, plan_id: str, *, now: datetime
) -> str:
    """Explicit action: create sequence 0, update accepted with +1, otherwise deduplicate."""

    if re.fullmatch(r"trip_[A-Za-z0-9_-]{1,120}", plan_id) is None:
        raise ValueError("trip plan identifier is invalid")
    ensure_trip_calendar_tables(connection)
    validate_trip_calendar_integrity(connection)
    connection.execute("BEGIN TRANSACTION")
    try:
        outbox_id = _enqueue_trip_invite_in_transaction(connection, plan_id, now=now)
        connection.execute("COMMIT")
        return outbox_id
    except Exception:
        connection.execute("ROLLBACK")
        raise


def claim_trip_outbox(connection: duckdb.DuckDBPyConnection, *, now: datetime) -> TripClaim | None:
    connection.execute("BEGIN TRANSACTION")
    try:
        ensure_trip_calendar_tables(connection)
        validate_trip_calendar_integrity(connection)
        timestamp = _iso(now)
        ambiguous = connection.execute(
            f"""SELECT outbox_id, trip_plan_id, claim_token, attempt_count
                FROM {TRIP_SCHEMA}.trip_outbox
                WHERE state='claimed' AND claim_expires_at <= ? AND send_started_at IS NOT NULL""",
            [timestamp],
        ).fetchall()
        for outbox_id, trip_plan_id, claim_token, attempt_count in ambiguous:
            connection.execute(
                f"""UPDATE {TRIP_SCHEMA}.trip_outbox SET state='delivery_unknown',
                    claim_token=NULL, claimed_at=NULL, claim_expires_at=NULL, updated_at=?,
                    safe_terminal_reason='crashed_after_send_started' WHERE outbox_id=?""",
                [timestamp, outbox_id],
            )
            connection.execute(
                f"""UPDATE {TRIP_SCHEMA}.trip_event_intents SET status='delivery_unknown',
                    updated_at=? WHERE trip_plan_id=? AND current_outbox_id=?""",
                [timestamp, trip_plan_id, outbox_id],
            )
            connection.execute(
                f"""INSERT INTO {TRIP_SCHEMA}.trip_outbox_attempts
                    VALUES (?, ?, ?, ?, 'delivery_unknown',
                            'crashed_after_send_started', ?)""",
                [
                    f"trip_attempt_{uuid.uuid4().hex}",
                    outbox_id,
                    int(attempt_count) + 1,
                    claim_token,
                    timestamp,
                ],
            )
        expired = connection.execute(
            f"""SELECT outbox_id, claim_token, attempt_count FROM {TRIP_SCHEMA}.trip_outbox
                WHERE state='claimed' AND claim_expires_at <= ? AND send_started_at IS NULL""",
            [timestamp],
        ).fetchall()
        for outbox_id, token, attempts in expired:
            connection.execute(
                f"""UPDATE {TRIP_SCHEMA}.trip_outbox SET state='pending', claim_token=NULL,
                    claimed_at=NULL, claim_expires_at=NULL, updated_at=? WHERE outbox_id=?""",
                [timestamp, outbox_id],
            )
            connection.execute(
                f"""INSERT INTO {TRIP_SCHEMA}.trip_outbox_attempts
                    VALUES (?, ?, ?, ?, 'claim_recovered', 'expired_pre_send_claim', ?)""",
                [f"trip_attempt_{uuid.uuid4().hex}", outbox_id, int(attempts), token, timestamp],
            )
        rows = connection.execute(
            f"""SELECT outbox.outbox_id, outbox.payload_json, outbox.payload_hash,
                       outbox.source_plan_hash, outbox.attempt_count
                FROM {TRIP_SCHEMA}.trip_outbox AS outbox
                JOIN {TRIP_SCHEMA}.trip_event_intents AS intent
                  ON intent.trip_plan_id=outbox.trip_plan_id
                 AND intent.event_uid=outbox.event_uid
                 AND intent.sequence=outbox.sequence
                 AND intent.current_outbox_id=outbox.outbox_id
                 AND intent.source_plan_hash=outbox.source_plan_hash
                WHERE outbox.state IN ('pending','retry_wait') AND outbox.next_attempt_at <= ?
                ORDER BY outbox.next_attempt_at, outbox.created_at LIMIT 1""",
            [timestamp],
        ).fetchall()
        if not rows:
            connection.execute("COMMIT")
            return None
        row = rows[0]
        payload = TripCalendarPayload.model_validate_json(str(row[1]))
        if payload.payload_hash != str(row[2]) or payload.source_plan_hash != str(row[3]):
            raise ValueError("trip outbox payload integrity check failed")
        current_hash = str(_canonical_source(connection, payload.trip_plan_id)["source_plan_hash"])
        if current_hash != payload.source_plan_hash:
            raise ValueError("trip plan changed after invite creation")
        token = uuid.uuid4().hex
        expires = _iso(now + CLAIM_TTL)
        claimed = connection.execute(
            f"""UPDATE {TRIP_SCHEMA}.trip_outbox
                SET state='claimed', claim_token=?, claimed_at=?, claim_expires_at=?, updated_at=?
                WHERE outbox_id=? AND state IN ('pending','retry_wait')
                RETURNING outbox_id""",
            [token, timestamp, expires, timestamp, row[0]],
        ).fetchone()
        if claimed is None:
            connection.execute("ROLLBACK")
            return None
        connection.execute("COMMIT")
        return TripClaim(str(claimed[0]), token, payload, int(row[4]))
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _attempt(
    connection: duckdb.DuckDBPyConnection,
    claim: TripClaim,
    *,
    phase: str,
    now: datetime,
    reason: str,
    next_at: datetime | None = None,
) -> None:
    timestamp = _iso(now)
    terminal = timestamp if phase in {"accepted", "failed"} else None
    state = phase
    connection.execute("BEGIN TRANSACTION")
    try:
        row = connection.execute(
            f"SELECT state, claim_token FROM {TRIP_SCHEMA}.trip_outbox WHERE outbox_id=?",
            [claim.outbox_id],
        ).fetchone()
        if row is None or str(row[0]) != "claimed" or str(row[1]) != claim.claim_token:
            raise ValueError("trip outbox claim is stale")
        connection.execute(
            f"""UPDATE {TRIP_SCHEMA}.trip_outbox SET state=?, next_attempt_at=?,
                attempt_count=attempt_count+1, claim_token=NULL, claimed_at=NULL,
                claim_expires_at=NULL, updated_at=?, terminal_at=?, safe_terminal_reason=?
                WHERE outbox_id=?""",
            [
                state,
                _iso(next_at) if next_at else timestamp,
                timestamp,
                terminal,
                reason,
                claim.outbox_id,
            ],
        )
        connection.execute(
            f"INSERT INTO {TRIP_SCHEMA}.trip_outbox_attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                f"trip_attempt_{uuid.uuid4().hex}",
                claim.outbox_id,
                claim.attempt_count + 1,
                claim.claim_token,
                phase,
                reason,
                timestamp,
            ],
        )
        if phase == "accepted":
            connection.execute(
                f"""INSERT INTO {TRIP_SCHEMA}.trip_accepted_snapshots VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_uid) DO UPDATE SET trip_plan_id=excluded.trip_plan_id,
                    accepted_sequence=excluded.accepted_sequence,
                    payload_json=excluded.payload_json,
                    payload_hash=excluded.payload_hash, accepted_at=excluded.accepted_at
                    WHERE excluded.accepted_sequence > trip_accepted_snapshots.accepted_sequence""",
                [
                    claim.payload.event_uid,
                    claim.payload.trip_plan_id,
                    claim.payload.sequence,
                    claim.payload.canonical_json(),
                    claim.payload.payload_hash,
                    timestamp,
                ],
            )
            connection.execute(
                f"""UPDATE {TRIP_SCHEMA}.trip_event_intents SET status='accepted',
                    accepted_sequence=CASE WHEN accepted_sequence IS NULL OR accepted_sequence < ?
                                           THEN ? ELSE accepted_sequence END,
                    updated_at=? WHERE trip_plan_id=? AND sequence=?""",
                [
                    claim.payload.sequence,
                    claim.payload.sequence,
                    timestamp,
                    claim.payload.trip_plan_id,
                    claim.payload.sequence,
                ],
            )
        elif phase in {"failed", "delivery_unknown"}:
            connection.execute(
                f"""UPDATE {TRIP_SCHEMA}.trip_event_intents SET status=?, updated_at=?
                    WHERE trip_plan_id=? AND sequence=?""",
                [phase, timestamp, claim.payload.trip_plan_id, claim.payload.sequence],
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _ical_escape(value: str) -> str:
    _safe_text(value, "calendar text", 10000)
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    chunks: list[str] = []
    current = ""
    for character in line:
        if len((current + character).encode()) > 75:
            chunks.append(current)
            current = " " + character
        else:
            current += character
    chunks.append(current)
    return "\r\n".join(chunks)


def _ical_time(value: str) -> str:
    return _parse_time(value).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_trip_icalendar(payload: TripCalendarPayload, *, organizer: str, attendee: str) -> str:
    # Defense in depth for callers that bypass Pydantic construction/assignment validation.
    _validate_calendar_description_text(payload.field_plan_text)
    for caveat in payload.caveats:
        _validate_calendar_description_text(caveat)
    address = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9.-]{1,190}")
    if address.fullmatch(organizer) is None or address.fullmatch(attendee) is None:
        raise ValueError("email address is invalid")
    location = payload.location_name[:120]
    summary = f"Rufous trip — {location}"
    targets = ", ".join(payload.target_common_names)
    caveats = "\n".join(f"- {item}" for item in payload.caveats) or "- None recorded"
    description = (
        f"Field plan:\n{payload.field_plan_text}\n\nTargets (ordered): {targets}\n"
        f"Weather: {payload.weather_status}\nEvidence caveats:\n{caveats}\n"
        "Local product caveat: Rufous is local planning support; verify current access, "
        "conditions, and bird presence before visiting."
    )
    if len(description) > 12000:
        raise ValueError("calendar description exceeds its bound")
    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Rufous//Trip Plan//EN",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "X-WR-TIMEZONE:America/Phoenix",
        "BEGIN:VEVENT",
        f"UID:{_ical_escape(payload.event_uid)}",
        f"SEQUENCE:{payload.sequence}",
        f"DTSTAMP:{_ical_time(payload.dtstamp)}",
        f"DTSTART:{_ical_time(payload.window_start)}",
        f"DTEND:{_ical_time(payload.window_end)}",
        f"ORGANIZER:mailto:{organizer}",
        f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{attendee}",
        f"SUMMARY:{_ical_escape(summary)}",
        f"DESCRIPTION:{_ical_escape(description)}",
        f"LOCATION:{_ical_escape(payload.location_name)}",
        f"GEO:{payload.latitude:.6f};{payload.longitude:.6f}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def build_trip_calendar_mime(
    payload: TripCalendarPayload, *, organizer: str, attendee: str
) -> EmailMessage:
    calendar = build_trip_icalendar(payload, organizer=organizer, attendee=attendee)
    message = EmailMessage(policy=SMTP)
    message["From"] = organizer
    message["To"] = attendee
    message["Subject"] = f"Rufous trip update: {payload.location_name[:120]}"
    message["Date"] = _parse_time(payload.dtstamp)
    message["Message-ID"] = f"<{_outbox_id(payload.event_uid, payload.sequence)}@local>"
    message.set_content("Your Rufous trip plan is attached as a calendar invitation.")
    message.add_alternative(
        calendar, subtype="calendar", charset="utf-8", params={"method": "REQUEST"}
    )
    message.set_boundary("rufous-" + payload.payload_hash[:32])
    return message


def deliver_next_trip_outbox(
    connection: duckdb.DuckDBPyConnection,
    *,
    settings: BirdAlertSmtpSettings,
    now: datetime,
    smtp_factory: SmtpFactory = smtplib.SMTP,
) -> DeliveryResult:
    """Explicit fakeable sender; it never runs unless directly invoked by a POST/command."""

    config = settings.runtime()
    claim = claim_trip_outbox(connection, now=now)
    if claim is None:
        return DeliveryResult("idle", None, None)
    try:
        client = _prepare(config, smtp_factory)
    except Exception as exc:
        classification = _response_class(exc)
        if classification == "permanent" or isinstance(exc, ssl.SSLError | ValueError):
            _attempt(
                connection,
                claim,
                phase="failed",
                now=now,
                reason="smtp_configuration_or_auth_rejected",
            )
            return DeliveryResult("failed", claim.outbox_id, "smtp_configuration_or_auth_rejected")
        retry_number = claim.attempt_count
        if retry_number < len(RETRY_DELAYS):
            next_at = now + RETRY_DELAYS[retry_number]
            _attempt(
                connection,
                claim,
                phase="retry_wait",
                now=now,
                reason="smtp_pre_acceptance_transient",
                next_at=next_at,
            )
            return DeliveryResult(
                "retry_wait", claim.outbox_id, "smtp_pre_acceptance_transient", _iso(next_at)
            )
        _attempt(
            connection,
            claim,
            phase="failed",
            now=now,
            reason="smtp_pre_acceptance_retries_exhausted",
        )
        return DeliveryResult("failed", claim.outbox_id, "smtp_pre_acceptance_retries_exhausted")

    timestamp = _iso(now)
    connection.execute(
        f"""UPDATE {TRIP_SCHEMA}.trip_outbox SET send_started_at=?, updated_at=?
            WHERE outbox_id=? AND state='claimed' AND claim_token=?""",
        [timestamp, timestamp, claim.outbox_id, claim.claim_token],
    )
    connection.execute(
        f"""INSERT INTO {TRIP_SCHEMA}.trip_outbox_attempts
            VALUES (?, ?, ?, ?, 'send_started', NULL, ?)""",
        [
            f"trip_attempt_{uuid.uuid4().hex}",
            claim.outbox_id,
            claim.attempt_count + 1,
            claim.claim_token,
            timestamp,
        ],
    )
    try:
        refused = client.send_message(
            build_trip_calendar_mime(
                claim.payload, organizer=config.organizer, attendee=config.recipient
            )
        )
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    except Exception as exc:
        _close(client)
        classification = _response_class(exc)
        if classification == "transient" and claim.attempt_count < len(RETRY_DELAYS):
            next_at = now + RETRY_DELAYS[claim.attempt_count]
            _attempt(
                connection,
                claim,
                phase="retry_wait",
                now=now,
                reason="smtp_explicit_transient_rejection",
                next_at=next_at,
            )
            return DeliveryResult(
                "retry_wait", claim.outbox_id, "smtp_explicit_transient_rejection", _iso(next_at)
            )
        if classification is not None:
            reason = (
                "smtp_transient_retries_exhausted"
                if classification == "transient"
                else "smtp_explicit_permanent_rejection"
            )
            _attempt(connection, claim, phase="failed", now=now, reason=reason)
            return DeliveryResult("failed", claim.outbox_id, reason)
        _attempt(
            connection, claim, phase="delivery_unknown", now=now, reason="smtp_acceptance_ambiguous"
        )
        return DeliveryResult("delivery_unknown", claim.outbox_id, "smtp_acceptance_ambiguous")
    _close(client)
    _attempt(connection, claim, phase="accepted", now=now, reason="smtp_bridge_accepted")
    return DeliveryResult("accepted", claim.outbox_id, "smtp_bridge_accepted")


def trip_invite_status(connection: duckdb.DuckDBPyConnection, plan_id: str) -> dict[str, object]:
    try:
        row = connection.execute(
            f"""SELECT intent.event_uid, intent.sequence, intent.status, intent.current_outbox_id,
                       outbox.state, outbox.attempt_count, outbox.updated_at
                FROM {TRIP_SCHEMA}.trip_event_intents intent
                LEFT JOIN {TRIP_SCHEMA}.trip_outbox outbox
                  ON outbox.outbox_id=intent.current_outbox_id WHERE intent.trip_plan_id=?""",
            [plan_id],
        ).fetchone()
    except duckdb.CatalogException:
        row = None
    if row is None:
        return {
            "status": "not_created",
            "sequence": None,
            "outbox_id": None,
            "allowed_actions": ["send"],
            "can_retry": False,
            "updated_at": None,
        }
    status = str(row[4] or row[2])
    actions: list[str] = []
    if status == "accepted":
        actions = ["send_update"]
    elif status == "failed":
        actions = ["retry_failed"]
    elif status == "delivery_unknown":
        actions = ["mark_delivered", "mark_not_delivered_and_retry"]
    return {
        "status": status,
        "sequence": int(row[1]),
        "outbox_id": str(row[3]),
        "allowed_actions": actions,
        "can_retry": status == "failed",
        "updated_at": str(row[6]) if row[6] is not None else None,
    }


def reconcile_trip_invite(
    connection: duckdb.DuckDBPyConnection,
    outbox_id: str,
    *,
    outcome: Literal["delivered", "not_delivered", "retry_failed"],
    now: datetime,
) -> str:
    """Idempotent explicit reconciliation; replacement creation is atomic."""

    ensure_trip_calendar_tables(connection)
    validate_trip_calendar_integrity(connection)
    row = connection.execute(
        f"SELECT state, payload_json FROM {TRIP_SCHEMA}.trip_outbox WHERE outbox_id=?",
        [outbox_id],
    ).fetchone()
    if row is None:
        raise ValueError("trip outbox is unavailable")
    payload = TripCalendarPayload.model_validate_json(str(row[1]))
    if (
        str(_canonical_source(connection, payload.trip_plan_id)["source_plan_hash"])
        != payload.source_plan_hash
    ):
        raise ValueError("trip plan changed after invite creation")
    state = str(row[0])
    if outcome == "delivered":
        if state == "accepted":
            return outbox_id
        if state != "delivery_unknown":
            raise ValueError("trip delivery is not unknown")
        claim = TripClaim(outbox_id, f"manual_{uuid.uuid4().hex}", payload, 0)
        changed = connection.execute(
            f"""UPDATE {TRIP_SCHEMA}.trip_outbox SET state='claimed', claim_token=?
                WHERE outbox_id=? AND state='delivery_unknown' RETURNING outbox_id""",
            [claim.claim_token, outbox_id],
        ).fetchone()
        if changed is None:
            return reconcile_trip_invite(connection, outbox_id, outcome=outcome, now=now)
        _attempt(
            connection, claim, phase="accepted", now=now, reason="operator_confirmed_delivered"
        )
        return outbox_id
    if state == "superseded":
        current = connection.execute(
            f"""SELECT current_outbox_id FROM {TRIP_SCHEMA}.trip_event_intents
                WHERE trip_plan_id=? AND event_uid=? AND sequence>?""",
            [payload.trip_plan_id, payload.event_uid, payload.sequence],
        ).fetchone()
        if current is not None:
            return str(current[0])
    expected = "failed" if outcome == "retry_failed" else "delivery_unknown"
    if state != expected:
        raise ValueError(f"trip delivery is not {expected.replace('_', ' ')}")

    timestamp = _iso(now)
    connection.execute("BEGIN TRANSACTION")
    try:
        changed = connection.execute(
            f"""UPDATE {TRIP_SCHEMA}.trip_outbox SET state='superseded', terminal_at=?,
                updated_at=?, safe_terminal_reason='operator_retry'
                WHERE outbox_id=? AND state=? RETURNING outbox_id""",
            [timestamp, timestamp, outbox_id, expected],
        ).fetchone()
        if changed is None:
            raise ValueError("trip delivery reconciliation raced")
        connection.execute(
            f"""UPDATE {TRIP_SCHEMA}.trip_event_intents SET status='failed', updated_at=?
                WHERE trip_plan_id=? AND current_outbox_id=?""",
            [timestamp, payload.trip_plan_id, outbox_id],
        )
        replacement = _enqueue_trip_invite_in_transaction(connection, payload.trip_plan_id, now=now)
        connection.execute("COMMIT")
        return replacement
    except Exception:
        connection.execute("ROLLBACK")
        raise


def cleanup_trip_outbox(connection: duckdb.DuckDBPyConnection, *, now: datetime) -> int:
    """Retain unresolved unknown rows and minimal UID/sequence dedupe state."""

    ensure_trip_calendar_tables(connection)
    validate_trip_calendar_integrity(connection)
    cutoff = _iso(now - RESOLVED_RETENTION)
    rows = connection.execute(
        f"""SELECT outbox.outbox_id, outbox.event_uid, outbox.sequence,
                   outbox.payload_hash, outbox.terminal_at
            FROM {TRIP_SCHEMA}.trip_outbox AS outbox
            LEFT JOIN {TRIP_SCHEMA}.trip_event_intents AS intent
              ON intent.current_outbox_id=outbox.outbox_id
            WHERE outbox.terminal_at IS NOT NULL AND outbox.terminal_at < ?
              AND outbox.state IN ('accepted','failed','superseded')
              AND intent.trip_plan_id IS NULL""",
        [cutoff],
    ).fetchall()
    connection.execute("BEGIN TRANSACTION")
    try:
        for row in rows:
            connection.execute(
                f"INSERT OR IGNORE INTO {TRIP_SCHEMA}.trip_outbox_dedupe VALUES (?, ?, ?, ?, ?)",
                row,
            )
            connection.execute(
                f"DELETE FROM {TRIP_SCHEMA}.trip_outbox_attempts WHERE outbox_id=?", [row[0]]
            )
            connection.execute(f"DELETE FROM {TRIP_SCHEMA}.trip_outbox WHERE outbox_id=?", [row[0]])
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return len(rows)
