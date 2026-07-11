"""Trip calendar identity, canonical payload, outbox, API, delivery, and privacy gates."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import Any

import duckdb
import pytest
from databox.agent_tools.persistence import ensure_birding_agent_persistence_tables
from databox.api import create_app
from databox.bird_alert_delivery import BirdAlertSmtpSettings
from databox.trip_plan_calendar import (
    TRIP_SCHEMA,
    TripCalendarPayload,
    _attempt,
    _validate_calendar_description_text,
    build_trip_icalendar,
    canonical_trip_payload,
    claim_trip_outbox,
    cleanup_trip_outbox,
    deliver_next_trip_outbox,
    enqueue_trip_invite,
    ensure_trip_calendar_tables,
    reconcile_trip_invite,
    trip_invite_status,
    validate_trip_calendar_integrity,
)
from fastapi.testclient import TestClient

NOW = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)


def _plan(connection: duckdb.DuckDBPyConnection, plan_id: str = "trip_fixture") -> None:
    ensure_birding_agent_persistence_tables(connection)
    connection.execute(
        """INSERT INTO birding_agent.trip_plans VALUES
        (?, 'Madera Canyon', 'Madera Canyon Recreation Area', 31.7, -110.88, 'US-AZ',
         '2026-07-12T06:00:00-07:00', '2026-07-12T09:00:00-07:00', 180,
         'intermediate', NULL, 'complete', 'Start at the lower trail and scan oak edges.',
         '["Public observations do not guarantee presence."]', ?, ?)""",
        [plan_id, NOW.isoformat(), NOW.isoformat()],
    )
    connection.execute(
        """INSERT INTO birding_agent.trip_plan_recommendations VALUES
        (?, ?, 'lookup_1', 'eletro', 'Elegant Trogon', 'Trogon elegans',
         'target', 1, 'high', 'Recent public evidence.', '["Access can change."]', ?)""",
        [f"rec_{plan_id}", plan_id, NOW.isoformat()],
    )
    connection.execute(
        """INSERT INTO birding_agent.trip_plan_evidence VALUES
        (?, ?, NULL, 'open_meteo', NULL, NULL, 'weather', 'available',
         31.7, -110.88, '2026-07-12T06:00:00-07:00', '2026-07-12T09:00:00-07:00',
         ?, '{"timezone":"America/Phoenix"}', '{}', '["Forecasts can change."]')""",
        [f"weather_{plan_id}", plan_id, NOW.isoformat()],
    )


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "calendar.duckdb"
    connection = duckdb.connect(str(path))
    _plan(connection)
    connection.close()
    return path


def _ebird_evidence(
    connection: duckdb.DuckDBPyConnection,
    *,
    source_id: str | None,
    valid: bool = True,
    reviewed: bool = True,
    private: bool = False,
    duplicate: bool = False,
) -> None:
    connection.execute("CREATE SCHEMA IF NOT EXISTS environmental_observations")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS environmental_observations.fact_bird_observation (
        source_observation_id VARCHAR, is_valid BOOLEAN, is_reviewed BOOLEAN,
        is_location_private BOOLEAN)"""
    )
    if source_id is not None and source_id.strip():
        connection.execute(
            "INSERT INTO environmental_observations.fact_bird_observation VALUES (?, ?, ?, ?)",
            [source_id, valid, reviewed, private],
        )
        if duplicate:
            connection.execute(
                "INSERT INTO environmental_observations.fact_bird_observation VALUES (?, ?, ?, ?)",
                [source_id, valid, reviewed, private],
            )
    connection.execute(
        """INSERT INTO birding_agent.trip_plan_evidence VALUES
        ('ebird_fixture', 'trip_fixture', 'rec_trip_fixture', 'ebird',
         'environmental_observations.fact_bird_observation', ?, 'recent_observation',
         'available', 31.7, -110.88, '2026-07-12T06:00:00-07:00',
         '2026-07-12T09:00:00-07:00', ?, '{}', '{}', '[]')""",
        [source_id, NOW.isoformat()],
    )


def _settings(tmp_path: Path) -> BirdAlertSmtpSettings:
    certificate = tmp_path / "bridge.pem"
    certificate.write_text(
        "-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    return BirdAlertSmtpSettings(
        enabled="true",
        security="starttls",
        host="127.0.0.1",
        port="1025",
        username="sender@example.test",
        password="secret-never-rendered",
        organizer="sender@example.test",
        recipient="recipient@example.test",
        ca_file=str(certificate),
    )


class FakeSmtp:
    def __init__(self) -> None:
        self.messages: list[Any] = []

    def send_message(self, message: Any) -> dict[str, object]:
        self.messages.append(message)
        return {}

    def quit(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_stable_uid_sequence_canonical_request_and_separate_relationships(
    database: Path,
) -> None:
    connection = duckdb.connect(str(database))
    first = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    repeated_pending = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    assert repeated_pending == first
    row = connection.execute(
        f"""SELECT event_kind, trip_plan_id, event_uid, sequence, method, payload_json
            FROM {TRIP_SCHEMA}.trip_outbox"""
    ).fetchone()
    assert row is not None
    assert row[:2] == ("trip_plan", "trip_fixture")
    assert row[3:5] == (0, "REQUEST")
    payload = TripCalendarPayload.model_validate_json(row[5])
    assert payload.target_common_names == ["Elegant Trogon"]
    assert payload.weather_status == "available"
    assert any("Public observations" in item for item in payload.caveats)
    assert connection.execute(f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox").fetchone() == (1,)
    columns = {
        item[0]
        for item in connection.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema='birding_calendar' AND table_name='trip_outbox'"""
        ).fetchall()
    }
    assert {"watch_id", "activation_generation", "species_code"}.isdisjoint(columns)
    connection.close()


def test_calendar_is_bounded_folded_injection_safe_and_private(database: Path) -> None:
    connection = duckdb.connect(str(database))
    uid = "rufous-trip-" + "a" * 64 + "@local"
    payload = canonical_trip_payload(connection, "trip_fixture", event_uid=uid, sequence=0, now=NOW)
    calendar = build_trip_icalendar(
        payload, organizer="sender@example.test", attendee="recipient@example.test"
    )
    assert "METHOD:REQUEST" in calendar
    assert "SUMMARY:Rufous trip — Madera Canyon Recreation Area" in calendar
    assert "DTSTART:20260712T130000Z" in calendar
    assert "DTEND:20260712T160000Z" in calendar
    assert "UID:" + uid in calendar.replace("\r\n ", "")
    assert "secret" not in calendar.lower()
    assert "payload_json" not in calendar
    assert all(len(line.encode()) <= 75 for line in calendar.split("\r\n") if line)
    connection.close()


@pytest.mark.parametrize(
    ("column", "injected"),
    [
        ("field_plan_text", "Contact FiEld.User+tag @ Example.COM before departure."),
        ("caveats_json", "Alternate guide: other.person@example.test"),
        ("field_plan_text", "Contact field.user@example . com before departure."),
        ("field_plan_text", "rEcIpIeNt   : private party"),
        ("field_plan_text", "API key is supersecretvalue"),
        ("caveats_json", "Secret is supersecretvalue"),
        ("field_plan_text", "Recipient is Alice Smith"),
        ("caveats_json", "Attendee is private party"),
        ("field_plan_text", "API _ KEY = calendar-secret-value"),
        ("caveats_json", "credential : encoded-private-value"),
        ("field_plan_text", "access%2520token%253Dencoded-secret"),
        ("caveats_json", "Authorization Bearer private-token-value"),
        ("field_plan_text", "Open h T t P s : / / private.example/media.jpg"),
        ("caveats_json", "http://private.example/arbitrary"),
        ("field_plan_text", "%2568%2574%2574%2570%2573%253A%252F%252Fprivate.example/x"),
        ("field_plan_text", "www.private.example/nest.jpg"),
        ("caveats_json", "ftp://private.example/nest.jpg"),
        ("field_plan_text", "custom+private://private.example/nest.jpg"),
        ("caveats_json", "private.example/nest.jpg"),
        ("field_plan_text", "private.example?file=nest.jpg"),
        ("caveats_json", "private.example/"),
        ("field_plan_text", "private.example:8080/nest.jpg"),
        ("caveats_json", "www.private.example"),
        ("field_plan_text", "private.xyz/nest.jpg"),
        ("caveats_json", "private。example/nest.jpg"),
        ("field_plan_text", "www%252Eprivate%252Eexample%252Fnest%252Ejpg"),
        ("caveats_json", "client_secret=private-value"),
        ("field_plan_text", "smtp_password : private-value"),
        ("caveats_json", "refresh_token=private-value"),
        ("field_plan_text", "calendar-private-key=private-value"),
        ("caveats_json", "tripApiKeyValue=private-value"),
        ("field_plan_text", "private_key_hint=private-value"),
        ("caveats_json", "secretclient=private-value"),
        ("field_plan_text", "passwordstore=private-value"),
        ("caveats_json", "passwdcache=private-value"),
        ("field_plan_text", "tokenvalue=private-value"),
        ("caveats_json", "apiclient=private-value"),
        ("field_plan_text", "privatecredential=private-value"),
        ("caveats_json", "accesscredential=private-value"),
        ("field_plan_text", "authclient=private-value"),
        ("caveats_json", "client_secret is private-value"),
        ("field_plan_text", "passwordless=true"),
        ("caveats_json", "tokenization=enabled"),
        ("field_plan_text", "client%255Fsecret%253Dprivate-value"),
        ("field_plan_text", "Meet at 31.7000%252C%2520-110.8800 before dawn."),
        ("caveats_json", "Coordinates: 31.7000&#44; -110.8800"),
        ("field_plan_text", "Coordinates: -33.8688,151.2093"),
        ("caveats_json", "Coordinates: 51.5074,0.1278"),
        ("field_plan_text", "Coordinates: 51.50,0.12"),
        ("caveats_json", "Coordinates: 34,112"),
        ("field_plan_text", "gPs : +34, +112"),
        ("caveats_json", "LAT / LON = 34.5, 112.4"),
        ("field_plan_text", "latitude - longitude is -90, -180"),
        ("field_plan_text", "Coordinates are 34, 112"),
        ("caveats_json", "GPS — 34,112"),
        ("field_plan_text", "lat-lon at 34,112"),
        ("caveats_json", "LAT & LON: 34, 112"),
        ("field_plan_text", "Lat, Lon: 34, 112"),
        ("caveats_json", "latitude and longitude = 34, 112"),
        ("field_plan_text", "GPS:\n    34, 112"),
        ("caveats_json", "Coordinates (WGS84): 34, 112"),
        ("caveats_json", "COORDINATES   FOR SITE ARE : 34, 112"),
        ("field_plan_text", "Latitude / Longitude for the roost is (0, 180)"),
        ("field_plan_text", "guide @ localhost"),
        ("caveats_json", "guide @ [ 127.0.0.1 ]"),
        ("field_plan_text", "guide @ [ IPv6 : 2001 : db8 : : 1 ]"),
        ("caveats_json", "Recipient — Alice Smith"),
        ("field_plan_text", "Attendee (primary) – private party"),
        ("caveats_json", "Organizer (backup contact) ‐ private party"),
        ("field_plan_text", "API key (production) — private-value"),
        ("caveats_json", "Password (SMTP bridge) – private-value"),
        ("field_plan_text", "client—secret = private-value"),
        ("caveats_json", "Coordinates: 31.7000; -110.8800"),
        ("field_plan_text", "GPS: 31.7 / -110.8"),
        ("caveats_json", "31.7 N, 110.8 W"),
        ("field_plan_text", "31.7 S / 110.8 E"),
        ("caveats_json", "Coordinates (WGS84): 31 N; 110 W"),
        ("field_plan_text", "Recipient / Alice Smith"),
        ("caveats_json", "Recipient; Alice Smith"),
        ("field_plan_text", "Password / private-value"),
        ("caveats_json", "31.7 N / 110.8"),
        ("field_plan_text", "31.7 / 110.8 W"),
        ("caveats_json", "31.7 N and 110.8 W"),
        ("field_plan_text", "31.7° N, 110.8° W"),
        ("caveats_json", "31.7N 110.8W"),
        ("field_plan_text", "31.7 N & 110.8 W"),
        ("caveats_json", "31.7 N to 110.8 W"),
        ("field_plan_text", "31.7º N — 110.8º W"),
        ("caveats_json", "31.7˚N | 110.8˚W"),
        ("field_plan_text", "31.7 N (WGS84 / EPSG:4326) 110.8 W"),
        ("caveats_json", "31.7° N\nEPSG:4326:\n110.8° W"),
        ("caveats_json", "-----BEGIN PRIVATE KEY----- hidden"),
    ],
)
def test_prohibited_description_markers_fail_before_calendar_writes(
    database: Path, column: str, injected: str
) -> None:
    connection = duckdb.connect(str(database))
    value = json.dumps([injected]) if column == "caveats_json" else injected
    connection.execute(
        f"UPDATE birding_agent.trip_plans SET {column}=? WHERE trip_plan_id='trip_fixture'",
        [value],
    )

    with pytest.raises(ValueError, match="prohibited data"):
        enqueue_trip_invite(connection, "trip_fixture", now=NOW)

    for table in ("trip_event_intents", "trip_outbox", "trip_outbox_attempts"):
        assert connection.execute(f"SELECT count(*) FROM {TRIP_SCHEMA}.{table}").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM birding_alerts.runtime_settings WHERE setting_key='installation_id'"
    ).fetchone() == (0,)
    connection.close()


@pytest.mark.parametrize(
    "injected",
    [
        "API key is supersecretvalue",
        "Secret is supersecretvalue",
        "Recipient is Alice Smith",
        "Attendee is private party",
        "field.user@example . com",
        "www.private.example/nest.jpg",
        "ftp://private.example/nest.jpg",
        "private.example/nest.jpg",
        "private.example?file=nest.jpg",
        "private.example/",
        "private.example:8080/nest.jpg",
        "private.xyz/nest.jpg",
        "private。example/nest.jpg",
        "client_secret=private-value",
        "smtp_password=private-value",
        "refresh_token=private-value",
        "secretclient=private-value",
        "passwordstore=private-value",
        "passwdcache=private-value",
        "tokenvalue=private-value",
        "apiclient=private-value",
        "privatecredential=private-value",
        "accesscredential=private-value",
        "authclient=private-value",
        "client_secret is private-value",
        "guide @ localhost",
        "guide @ [ 127.0.0.1 ]",
        "guide @ [ IPv6 : 2001 : db8 : : 1 ]",
        "Recipient — Alice Smith",
        "Attendee (primary) – private party",
        "Organizer (backup contact) ‐ private party",
        "API key (production) — private-value",
        "Password (SMTP bridge) – private-value",
        "client—secret = private-value",
        "Coordinates: 31.7000; -110.8800",
        "GPS: 31.7 / -110.8",
        "31.7 N, 110.8 W",
        "31.7 S / 110.8 E",
        "Coordinates (WGS84): 31 N; 110 W",
        "Recipient / Alice Smith",
        "Recipient; Alice Smith",
        "Password / private-value",
        "31.7 N / 110.8",
        "31.7 / 110.8 W",
        "31.7 N and 110.8 W",
        "31.7° N, 110.8° W",
        "31.7N 110.8W",
        "31.7 N & 110.8 W",
        "31.7 N to 110.8 W",
        "31.7º N — 110.8º W",
        "31.7˚N | 110.8˚W",
        "31.7 N (WGS84 / EPSG:4326) 110.8 W",
        "31.7° N\nEPSG:4326:\n110.8° W",
        "Coordinates: -33.8688,151.2093",
        "Coordinates: 51.5074,0.1278",
        "Coordinates: 51.50,0.12",
        "Coordinates: 34,112",
        "gPs : +34, +112",
        "LAT / LON = 34.5, 112.4",
    ],
)
def test_builder_rejects_payload_created_through_validation_bypass(
    database: Path, injected: str
) -> None:
    connection = duckdb.connect(str(database))
    payload = canonical_trip_payload(
        connection,
        "trip_fixture",
        event_uid="rufous-trip-" + "c" * 64 + "@local",
        sequence=0,
        now=NOW,
    )
    bypassed = payload.model_copy(update={"caveats": [injected]})
    with pytest.raises(ValueError, match="prohibited data"):
        build_trip_icalendar(
            bypassed, organizer="sender@example.test", attendee="recipient@example.test"
        )
    connection.close()


@pytest.mark.parametrize(
    "safe_text",
    [
        "Coordinates are unavailable.",
        "GPS — pending field verification.",
        "lat-lon for site is intentionally omitted.",
        "Coordinates for site are 90.1, 0.",
        "GPS at 0, 180.1 is outside the valid range.",
        "Latitude / longitude: 91, 181.",
        "Coordinates are unavailable; walk 1, 2 miles.",
        "GPS is unavailable. Walk 1, 2 miles.",
        "Coordinates are unavailable; walk 1; 2 miles.",
        "Coordinates: 91 N; 110 W are invalid.",
        "Coordinates: 31 N; 181 W are invalid.",
        "Coordinates: 91 N and 110 W are invalid.",
        "Coordinates: 31° N and 181° W are invalid.",
        "The invalid grid example is 91N 181W.",
        "Northbound distance is 31.7 and westbound distance is 110.8 miles.",
        "Travel 31.7 N miles; the western trail remains open.",
        "The ranger counted 31.7 northern miles and 110.8 western miles.",
        "Degree symbols ° and º may appear in ordinary educational prose.",
        "31.7 N (WGS84 / EPSG:4326) longitude unavailable.",
        "Coordinates: 91 N (EPSG:4326) 110 W are invalid.",
        "Coordinates: 31 N (EPSG:4326) 181 W are invalid.",
        "31.7 N xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx 110.8 W",
        "The route is 1 / 2 mile on marked trails.",
    ],
)
def test_coordinate_label_false_positives_remain_accepted(safe_text: str) -> None:
    assert _validate_calendar_description_text(safe_text) == safe_text


@pytest.mark.parametrize(
    "safe_text",
    [
        "Observe the scientific name Trogon elegans before field use.",
        "Call the package module function from the local tool.",
        "Compare release v1.2/path before field use.",
        "Write www. when explaining the abbreviation.",
        "The protocol: ftp access is disabled.",
        "author=Audubon is a catalog note.",
        "authentication=required is an access policy, not a credential.",
        "oauth=disabled is an access policy.",
        "monkey=nearby is an ordinary observation note.",
        "access is limited in winter.",
        "private access is limited to marked trails.",
        "The refresh token count is zero.",
        "A secretive bird may use the key trail.",
    ],
)
def test_url_and_credential_false_positive_boundaries_remain_accepted(safe_text: str) -> None:
    assert _validate_calendar_description_text(safe_text) == safe_text


@pytest.mark.parametrize(
    "url",
    [
        "www.birds.com",
        "birds.org/",
        "birds.net/nest.jpg",
        "birds.io?file=nest.jpg",
        "birds.edu:8080/nest.jpg",
        "www.birds.gov",
        "birds.us/path",
        "birds.example/path",
        "birds.test?query=value",
        "birds.invalid:8080",
        "www.birds.local",
        "birds.xyz/nest.jpg",
        "birds.photography/nest.jpg",
        "birds.abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijk/path",
        "genus.species/juvenile",
        "package.module/function",
    ],
)
def test_url_shaped_domains_use_general_syntactic_tlds(url: str) -> None:
    with pytest.raises(ValueError, match="prohibited data"):
        _validate_calendar_description_text(url)


def test_description_privacy_boundaries_preserve_normal_prose_and_identity(database: Path) -> None:
    connection = duckdb.connect(str(database))
    prose = (
        "Keep email notifications disabled. Use the key trail junction for secretive birds; "
        "the key is near the oak. Walk 1.5, 2.5 miles; compare versions 1.20, 2.40. "
        "Unlabeled grid values 34, 112 are identifiers, not a location. "
        "Out-of-range examples Coordinates: 90.1, 0; GPS: 0, 180.1; lat/lon: 91, 181. "
        "The date is 7/11/2026, and HTTPS access is not required. "
        "Recipient species and attendee counts vary by season."
    )
    connection.execute(
        "UPDATE birding_agent.trip_plans SET field_plan_text=? WHERE trip_plan_id='trip_fixture'",
        [prose],
    )
    first = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    repeated = enqueue_trip_invite(connection, "trip_fixture", now=NOW + timedelta(minutes=1))
    row = connection.execute(
        f"SELECT event_uid, sequence, payload_json, payload_hash FROM {TRIP_SCHEMA}.trip_outbox"
    ).fetchone()
    assert row is not None
    payload = TripCalendarPayload.model_validate_json(row[2])
    assert repeated == first
    assert row[0] == payload.event_uid
    assert row[1] == payload.sequence == 0
    assert row[3] == payload.payload_hash
    assert payload.field_plan_text == prose
    connection.close()


def test_unsafe_update_rolls_back_and_api_error_is_fixed_and_redacted(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeSmtp()
    monkeypatch.setattr("databox.trip_plan_calendar._prepare", lambda config, factory: fake)
    connection = duckdb.connect(str(database))
    original_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    deliver_next_trip_outbox(connection, settings=_settings(tmp_path), now=NOW)
    before = connection.execute(
        f"""SELECT event_uid, sequence, status, source_plan_hash, current_outbox_id
            FROM {TRIP_SCHEMA}.trip_event_intents"""
    ).fetchone()
    connection.execute(
        """UPDATE birding_agent.trip_plans
           SET field_plan_text='Media: https%3A%2F%2Fprivate.example%2Fnest.jpg'
           WHERE trip_plan_id='trip_fixture'"""
    )
    with pytest.raises(ValueError, match="prohibited data"):
        enqueue_trip_invite(connection, "trip_fixture", now=NOW + timedelta(minutes=1))
    assert (
        connection.execute(
            f"""SELECT event_uid, sequence, status, source_plan_hash, current_outbox_id
            FROM {TRIP_SCHEMA}.trip_event_intents"""
        ).fetchone()
        == before
    )
    assert before is not None and before[1:3] == (0, "accepted") and before[4] == original_id
    assert connection.execute(f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox").fetchone() == (1,)
    connection.close()

    client = TestClient(
        create_app(
            database_path=str(database),
            static_dir=tmp_path / "missing",
            trip_smtp_settings=_settings(tmp_path),
            trip_smtp_factory=lambda *a, **k: fake,
        )
    )
    response = client.post("/api/trip-plans/trip_fixture/calendar-invite?confirm=true")
    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "unsafe_calendar_content",
            "message": "Trip plan cannot be included in a calendar invitation",
        }
    }
    rendered = json.dumps(response.json()).lower()
    assert all(marker not in rendered for marker in ("private.example", "media:", "nest.jpg"))
    assert len(fake.messages) == 1


def test_fake_smtp_acceptance_and_update_reuse_uid(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = duckdb.connect(str(database))
    first_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    fake = FakeSmtp()
    monkeypatch.setattr("databox.trip_plan_calendar._prepare", lambda config, factory: fake)
    result = deliver_next_trip_outbox(
        connection, settings=_settings(tmp_path), now=NOW, smtp_factory=lambda *a, **k: fake
    )
    assert result.status == "accepted"
    assert len(fake.messages) == 1
    second_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW + timedelta(minutes=1))
    assert second_id != first_id
    rows = connection.execute(
        f"SELECT event_uid, sequence FROM {TRIP_SCHEMA}.trip_outbox ORDER BY sequence"
    ).fetchall()
    assert rows[0][0] == rows[1][0]
    assert [item[1] for item in rows] == [0, 1]
    connection.close()


def test_retry_schedule_and_post_send_ambiguity(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = duckdb.connect(str(database))
    enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    monkeypatch.setattr(
        "databox.trip_plan_calendar._prepare",
        lambda config, factory: (_ for _ in ()).throw(TimeoutError()),
    )
    expected = [1, 5, 15]
    current = NOW
    for minutes in expected:
        result = deliver_next_trip_outbox(connection, settings=_settings(tmp_path), now=current)
        assert result.status == "retry_wait"
        assert datetime.fromisoformat(result.next_attempt_at) == current + timedelta(
            minutes=minutes
        )
        current += timedelta(minutes=minutes)
    assert (
        deliver_next_trip_outbox(connection, settings=_settings(tmp_path), now=current).status
        == "failed"
    )

    # A separate plan proves that an exception after DATA begins is never auto-retried.
    _plan(connection, "trip_ambiguous")
    enqueue_trip_invite(connection, "trip_ambiguous", now=current)
    ambiguous = FakeSmtp()
    ambiguous.send_message = lambda message: (_ for _ in ()).throw(TimeoutError())  # type: ignore[method-assign]
    monkeypatch.setattr("databox.trip_plan_calendar._prepare", lambda config, factory: ambiguous)
    result = deliver_next_trip_outbox(connection, settings=_settings(tmp_path), now=current)
    assert result.status == "delivery_unknown"
    assert claim_trip_outbox(connection, now=current + timedelta(days=1)) is None
    connection.close()


def test_tamper_and_deletion_fail_closed_without_new_outbox(database: Path) -> None:
    connection = duckdb.connect(str(database))
    enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    connection.execute(
        """UPDATE birding_agent.trip_plans SET field_plan_text='changed'
           WHERE trip_plan_id='trip_fixture'"""
    )
    with pytest.raises(ValueError, match="changed"):
        claim_trip_outbox(connection, now=NOW)
    assert connection.execute(f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox").fetchone() == (1,)
    connection.execute("DELETE FROM birding_agent.trip_plans WHERE trip_plan_id='trip_fixture'")
    with pytest.raises(ValueError, match="unavailable|integrity"):
        enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    connection.close()


def test_unknown_requires_manual_reconciliation_and_retry_advances_sequence(database: Path) -> None:
    connection = duckdb.connect(str(database))
    outbox_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    claim = claim_trip_outbox(connection, now=NOW)
    assert claim is not None
    # Simulate the ambiguity transition at the durable boundary.
    connection.execute(
        f"""UPDATE {TRIP_SCHEMA}.trip_outbox SET state='delivery_unknown',
            safe_terminal_reason='smtp_acceptance_ambiguous' WHERE outbox_id=?""",
        [outbox_id],
    )
    connection.execute(
        f"""UPDATE {TRIP_SCHEMA}.trip_event_intents SET status='delivery_unknown'
            WHERE trip_plan_id='trip_fixture'"""
    )
    assert claim_trip_outbox(connection, now=NOW + timedelta(days=1)) is None
    retry_id = reconcile_trip_invite(
        connection, outbox_id, outcome="not_delivered", now=NOW + timedelta(minutes=1)
    )
    assert retry_id != outbox_id
    status = trip_invite_status(connection, "trip_fixture")
    assert status["sequence"] == 1
    assert status["status"] == "pending"
    connection.close()


def test_get_startup_and_plan_detail_never_send(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "databox.trip_plan_calendar._prepare",
        lambda config, factory: calls.append("smtp") or FakeSmtp(),
    )
    client = TestClient(
        create_app(
            database_path=str(database),
            static_dir=tmp_path / "missing",
            trip_smtp_settings=_settings(tmp_path),
        )
    )
    assert client.get("/api/trip-plans/trip_fixture").status_code == 200
    status = client.get("/api/trip-plans/trip_fixture/calendar-invite")
    assert status.status_code == 200
    assert status.json()["status"] == "not_created"
    assert calls == []
    connection = duckdb.connect(str(database), read_only=True)
    tables = connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='birding_calendar'"
    ).fetchone()
    assert tables == (0,)
    connection.close()


def test_explicit_confirmed_post_only_sends_once_with_fake_smtp(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeSmtp()
    monkeypatch.setattr("databox.trip_plan_calendar._prepare", lambda config, factory: fake)
    client = TestClient(
        create_app(
            database_path=str(database),
            static_dir=tmp_path / "missing",
            trip_smtp_settings=_settings(tmp_path),
            trip_smtp_factory=lambda *a, **k: fake,
        )
    )
    assert client.post("/api/trip-plans/trip_fixture/calendar-invite").status_code == 409
    assert fake.messages == []
    response = client.post("/api/trip-plans/trip_fixture/calendar-invite?confirm=true")
    assert response.status_code == 200, response.text
    assert response.json()["delivery"]["status"] == "accepted"
    assert response.json()["delivery"]["acceptance_notice"] == "Accepted by local mail bridge"
    assert len(fake.messages) == 1
    body = json.dumps(response.json()).lower()
    assert all(secret not in body for secret in ("sender@", "recipient@", "secret", "1025", "pem"))


@pytest.mark.parametrize(
    ("source_id", "valid", "reviewed", "private", "duplicate"),
    [
        (None, True, True, False, False),
        ("   ", True, True, False, False),
        ("missing", True, True, False, False),
        ("duplicate", True, True, False, True),
        ("private", True, True, True, False),
        ("invalid", False, True, False, False),
        ("unreviewed", True, False, False, False),
    ],
)
def test_tainted_ebird_evidence_is_ineligible(
    database: Path,
    source_id: str | None,
    valid: bool,
    reviewed: bool,
    private: bool,
    duplicate: bool,
) -> None:
    connection = duckdb.connect(str(database))
    _ebird_evidence(
        connection,
        source_id=source_id,
        valid=valid,
        reviewed=reviewed,
        private=private,
        duplicate=duplicate,
    )
    if source_id == "missing":
        connection.execute(
            """DELETE FROM environmental_observations.fact_bird_observation
               WHERE source_observation_id='missing'"""
        )
    with pytest.raises(ValueError, match="identity|ineligible"):
        enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    assert connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name='trip_outbox'"
    ).fetchone() == (1,)
    assert connection.execute(f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox").fetchone() == (0,)
    connection.close()


def test_eligible_ebird_identity_is_canonical_but_private_facts_are_not_rendered(
    database: Path,
) -> None:
    connection = duckdb.connect(str(database))
    _ebird_evidence(connection, source_id="private-source-identity")
    payload = canonical_trip_payload(
        connection,
        "trip_fixture",
        event_uid="rufous-trip-" + "b" * 64 + "@local",
        sequence=0,
        now=NOW,
    )
    rendered = build_trip_icalendar(
        payload, organizer="sender@example.test", attendee="recipient@example.test"
    )
    assert "private-source-identity" not in rendered
    assert "environmental_observations" not in rendered
    connection.close()


def test_arizona_window_rejects_non_arizona_offsets(database: Path) -> None:
    connection = duckdb.connect(str(database))
    connection.execute(
        """UPDATE birding_agent.trip_plans
           SET window_start='2026-07-12T13:00:00+00:00'
           WHERE trip_plan_id='trip_fixture'"""
    )
    with pytest.raises(ValueError, match="Arizona"):
        enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    connection.close()


def test_concurrent_explicit_actions_create_one_intent(database: Path) -> None:
    barrier = Barrier(2)

    def enqueue() -> str:
        connection = duckdb.connect(str(database))
        try:
            barrier.wait()
            return enqueue_trip_invite(connection, "trip_fixture", now=NOW)
        except duckdb.TransactionException:
            return "conflict"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: enqueue(), range(2)))
    assert sum(value.startswith("trip_outbox_") for value in outcomes) >= 1
    connection = duckdb.connect(str(database))
    assert connection.execute(
        f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_event_intents"
    ).fetchone() == (1,)
    assert connection.execute(f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox").fetchone() == (1,)
    connection.close()


def test_concurrent_claims_produce_one_claim(database: Path) -> None:
    setup = duckdb.connect(str(database))
    enqueue_trip_invite(setup, "trip_fixture", now=NOW)
    setup.close()
    barrier = Barrier(2)

    def claim() -> str:
        connection = duckdb.connect(str(database))
        try:
            barrier.wait()
            result = claim_trip_outbox(connection, now=NOW)
            return "claimed" if result is not None else "idle"
        except duckdb.TransactionException:
            return "conflict"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: claim(), range(2)))
    assert outcomes.count("claimed") == 1
    connection = duckdb.connect(str(database))
    assert connection.execute(
        f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox WHERE state='claimed'"
    ).fetchone() == (1,)
    assert connection.execute(f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox").fetchone() == (1,)
    connection.close()


def test_claim_lease_recovery_and_post_send_expiry(database: Path) -> None:
    connection = duckdb.connect(str(database))
    outbox_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    first = claim_trip_outbox(connection, now=NOW)
    assert first is not None
    recovered = claim_trip_outbox(connection, now=NOW + timedelta(minutes=6))
    assert recovered is not None and recovered.outbox_id == outbox_id
    phases = connection.execute(
        f"SELECT phase FROM {TRIP_SCHEMA}.trip_outbox_attempts ORDER BY occurred_at"
    ).fetchall()
    assert ("claim_recovered",) in phases
    connection.execute(
        f"""UPDATE {TRIP_SCHEMA}.trip_outbox
            SET send_started_at=?, claim_expires_at=? WHERE outbox_id=?""",
        [NOW.isoformat(), NOW.isoformat(), outbox_id],
    )
    assert claim_trip_outbox(connection, now=NOW + timedelta(minutes=7)) is None
    assert trip_invite_status(connection, "trip_fixture")["status"] == "delivery_unknown"
    connection.close()


def test_reconciliation_enqueue_is_atomic_and_idempotent(
    database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = duckdb.connect(str(database))
    outbox_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    connection.execute(
        f"UPDATE {TRIP_SCHEMA}.trip_outbox SET state='delivery_unknown' WHERE outbox_id=?",
        [outbox_id],
    )
    connection.execute(f"UPDATE {TRIP_SCHEMA}.trip_event_intents SET status='delivery_unknown'")
    monkeypatch.setattr(
        "databox.trip_plan_calendar._enqueue_trip_invite_in_transaction",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("synthetic enqueue failure")),
    )
    with pytest.raises(ValueError, match="synthetic"):
        reconcile_trip_invite(
            connection, outbox_id, outcome="not_delivered", now=NOW + timedelta(minutes=1)
        )
    assert connection.execute(
        f"SELECT state FROM {TRIP_SCHEMA}.trip_outbox WHERE outbox_id=?", [outbox_id]
    ).fetchone() == ("delivery_unknown",)
    assert trip_invite_status(connection, "trip_fixture")["status"] == "delivery_unknown"
    monkeypatch.undo()
    replacement = reconcile_trip_invite(
        connection, outbox_id, outcome="not_delivered", now=NOW + timedelta(minutes=1)
    )
    assert (
        reconcile_trip_invite(
            connection, outbox_id, outcome="not_delivered", now=NOW + timedelta(minutes=2)
        )
        == replacement
    )
    assert connection.execute(f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox").fetchone() == (2,)
    connection.close()


def test_retry_api_and_explicit_due_worker_actually_send(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = duckdb.connect(str(database))
    failed_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    connection.execute(
        f"""UPDATE {TRIP_SCHEMA}.trip_outbox SET state='failed', terminal_at=?,
            safe_terminal_reason='synthetic' WHERE outbox_id=?""",
        [NOW.isoformat(), failed_id],
    )
    connection.execute(f"UPDATE {TRIP_SCHEMA}.trip_event_intents SET status='failed'")
    connection.close()
    fake = FakeSmtp()
    monkeypatch.setattr("databox.trip_plan_calendar._prepare", lambda config, factory: fake)
    client = TestClient(
        create_app(
            database_path=str(database),
            static_dir=tmp_path / "missing",
            trip_smtp_settings=_settings(tmp_path),
            trip_smtp_factory=lambda *a, **k: fake,
        )
    )
    retry = client.post(f"/api/trip-calendar-deliveries/{failed_id}/retry?confirm=true")
    assert retry.status_code == 200, retry.text
    assert retry.json()["delivery"]["status"] == "accepted"
    assert len(fake.messages) == 1

    connection = duckdb.connect(str(database))
    _plan(connection, "trip_due")
    due_id = enqueue_trip_invite(connection, "trip_due", now=datetime.now(UTC))
    connection.close()
    due = client.post("/api/trip-calendar-deliveries/deliver-due?confirm=true")
    assert due.status_code == 200, due.text
    assert due.json()["outbox_id"] == due_id
    assert due.json()["delivery"]["status"] == "accepted"
    assert len(fake.messages) == 2

    connection = duckdb.connect(str(database))
    _plan(connection, "trip_unknown_api")
    unknown_id = enqueue_trip_invite(connection, "trip_unknown_api", now=datetime.now(UTC))
    connection.execute(
        f"UPDATE {TRIP_SCHEMA}.trip_outbox SET state='delivery_unknown' WHERE outbox_id=?",
        [unknown_id],
    )
    connection.execute(
        f"""UPDATE {TRIP_SCHEMA}.trip_event_intents SET status='delivery_unknown'
            WHERE trip_plan_id='trip_unknown_api'"""
    )
    connection.close()
    route = f"/api/trip-calendar-deliveries/{unknown_id}/mark-not-delivered-and-retry?confirm=true"
    reconciled = client.post(route)
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["delivery"]["status"] == "accepted"
    assert len(fake.messages) == 3
    repeated = client.post(route)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["outbox_id"] == reconciled.json()["outbox_id"]
    assert len(fake.messages) == 3


def test_accepted_snapshot_cannot_regress(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = duckdb.connect(str(database))
    fake = FakeSmtp()
    monkeypatch.setattr("databox.trip_plan_calendar._prepare", lambda config, factory: fake)
    first_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    assert (
        deliver_next_trip_outbox(connection, settings=_settings(tmp_path), now=NOW).status
        == "accepted"
    )
    second_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW + timedelta(minutes=1))
    assert (
        deliver_next_trip_outbox(
            connection, settings=_settings(tmp_path), now=NOW + timedelta(minutes=1)
        ).status
        == "accepted"
    )
    first_payload = TripCalendarPayload.model_validate_json(
        connection.execute(
            f"SELECT payload_json FROM {TRIP_SCHEMA}.trip_outbox WHERE outbox_id=?", [first_id]
        ).fetchone()[0]
    )
    connection.execute(
        f"""UPDATE {TRIP_SCHEMA}.trip_outbox SET state='claimed', claim_token='late'
            WHERE outbox_id=?""",
        [first_id],
    )
    _attempt(
        connection,
        type(
            "Claim",
            (),
            {
                "outbox_id": first_id,
                "claim_token": "late",
                "payload": first_payload,
                "attempt_count": 1,
            },
        )(),
        phase="accepted",
        now=NOW + timedelta(minutes=2),
        reason="late_acceptance",
    )
    snapshot = connection.execute(
        f"SELECT accepted_sequence FROM {TRIP_SCHEMA}.trip_accepted_snapshots"
    ).fetchone()
    intent = connection.execute(
        f"SELECT accepted_sequence, current_outbox_id FROM {TRIP_SCHEMA}.trip_event_intents"
    ).fetchone()
    assert snapshot == (1,)
    assert intent == (1, second_id)
    connection.close()


def test_cleanup_retains_current_intent_and_dedupe(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = duckdb.connect(str(database))
    fake = FakeSmtp()
    monkeypatch.setattr("databox.trip_plan_calendar._prepare", lambda config, factory: fake)
    first_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    deliver_next_trip_outbox(connection, settings=_settings(tmp_path), now=NOW)
    second_id = enqueue_trip_invite(connection, "trip_fixture", now=NOW + timedelta(minutes=1))
    deliver_next_trip_outbox(
        connection, settings=_settings(tmp_path), now=NOW + timedelta(minutes=1)
    )
    connection.execute(
        f"""UPDATE {TRIP_SCHEMA}.trip_outbox
            SET terminal_at='2026-01-01T00:00:00+00:00' WHERE outbox_id=?""",
        [first_id],
    )
    assert cleanup_trip_outbox(connection, now=NOW) == 1
    assert connection.execute(
        f"SELECT current_outbox_id, status FROM {TRIP_SCHEMA}.trip_event_intents"
    ).fetchone() == (second_id, "accepted")
    assert connection.execute(
        f"SELECT outbox_id FROM {TRIP_SCHEMA}.trip_outbox_dedupe"
    ).fetchone() == (first_id,)
    assert connection.execute(
        f"SELECT count(*) FROM {TRIP_SCHEMA}.trip_outbox_attempts WHERE outbox_id=?", [first_id]
    ).fetchone() == (0,)
    validate_trip_calendar_integrity(connection)
    connection.close()


def test_runtime_and_offline_migrations_are_equivalent_and_integrity_fails_closed(
    tmp_path: Path,
) -> None:
    runtime = duckdb.connect(str(tmp_path / "runtime.duckdb"))
    runtime.execute("CREATE SCHEMA birding_agent")
    runtime.execute("CREATE TABLE birding_agent.trip_plans (trip_plan_id VARCHAR)")
    ensure_trip_calendar_tables(runtime)
    offline = duckdb.connect(str(tmp_path / "offline.duckdb"))
    offline.execute("CREATE SCHEMA birding_agent")
    offline.execute("CREATE TABLE birding_agent.trip_plans (trip_plan_id VARCHAR)")
    offline.execute(Path("migrations/20260711_trip_plan_calendar.sql").read_text(encoding="utf-8"))

    def shape(connection: duckdb.DuckDBPyConnection) -> list[tuple[object, ...]]:
        return connection.execute(
            """SELECT table_name, ordinal_position, column_name, data_type, is_nullable
               FROM information_schema.columns WHERE table_schema='birding_calendar'
               ORDER BY table_name, ordinal_position"""
        ).fetchall()

    assert shape(runtime) == shape(offline)
    runtime.close()
    offline.close()

    path = tmp_path / "integrity.duckdb"
    connection = duckdb.connect(str(path))
    _plan(connection)
    enqueue_trip_invite(connection, "trip_fixture", now=NOW)
    connection.execute(f"UPDATE {TRIP_SCHEMA}.trip_event_intents SET current_outbox_id='missing'")
    with pytest.raises(ValueError, match="integrity"):
        validate_trip_calendar_integrity(connection)
    connection.close()
