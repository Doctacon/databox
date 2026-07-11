-- Additive DuckDB migration for trip-plan calendar invitations.
-- The application applies the same idempotent DDL in ensure_trip_calendar_tables.
CREATE SCHEMA IF NOT EXISTS birding_calendar;
CREATE SCHEMA IF NOT EXISTS birding_alerts;
CREATE TABLE IF NOT EXISTS birding_alerts.runtime_settings (
  setting_key VARCHAR PRIMARY KEY,
  setting_value VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS birding_calendar.trip_event_intents (
  trip_plan_id VARCHAR PRIMARY KEY,
  event_kind VARCHAR NOT NULL CHECK (event_kind = 'trip_plan'),
  event_uid VARCHAR NOT NULL UNIQUE,
  sequence BIGINT NOT NULL CHECK (sequence >= 0),
  status VARCHAR NOT NULL CHECK (status IN ('pending','accepted','failed','delivery_unknown')),
  source_plan_hash VARCHAR NOT NULL,
  current_outbox_id VARCHAR,
  accepted_sequence BIGINT CHECK (accepted_sequence IS NULL OR accepted_sequence >= 0),
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS birding_calendar.trip_outbox (
  outbox_id VARCHAR PRIMARY KEY,
  event_kind VARCHAR NOT NULL CHECK (event_kind = 'trip_plan'),
  trip_plan_id VARCHAR NOT NULL,
  event_uid VARCHAR NOT NULL,
  sequence BIGINT NOT NULL,
  method VARCHAR NOT NULL CHECK (method = 'REQUEST'),
  payload_json VARCHAR NOT NULL,
  payload_hash VARCHAR NOT NULL,
  source_plan_hash VARCHAR NOT NULL,
  state VARCHAR NOT NULL CHECK (state IN (
    'pending','claimed','retry_wait','accepted','failed','delivery_unknown','superseded'
  )),
  next_attempt_at VARCHAR NOT NULL,
  claim_token VARCHAR,
  claimed_at VARCHAR,
  claim_expires_at VARCHAR,
  send_started_at VARCHAR,
  attempt_count BIGINT NOT NULL CHECK (attempt_count >= 0),
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  terminal_at VARCHAR,
  safe_terminal_reason VARCHAR,
  UNIQUE (event_uid, sequence, method)
);
CREATE TABLE IF NOT EXISTS birding_calendar.trip_outbox_attempts (
  attempt_id VARCHAR PRIMARY KEY,
  outbox_id VARCHAR NOT NULL,
  attempt_number BIGINT NOT NULL,
  claim_token VARCHAR NOT NULL,
  phase VARCHAR NOT NULL CHECK (phase IN (
    'send_started','accepted','retry_wait','failed','delivery_unknown','claim_recovered'
  )),
  safe_reason VARCHAR,
  occurred_at VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS birding_calendar.trip_accepted_snapshots (
  event_uid VARCHAR PRIMARY KEY,
  trip_plan_id VARCHAR NOT NULL,
  accepted_sequence BIGINT NOT NULL,
  payload_json VARCHAR NOT NULL,
  payload_hash VARCHAR NOT NULL,
  accepted_at VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS birding_calendar.trip_outbox_dedupe (
  outbox_id VARCHAR PRIMARY KEY,
  event_uid VARCHAR NOT NULL,
  sequence BIGINT NOT NULL,
  payload_hash VARCHAR NOT NULL,
  terminal_at VARCHAR NOT NULL,
  UNIQUE (event_uid, sequence)
);
