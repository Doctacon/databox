import type { AlertDelivery, AlertDeliveryAttempt } from "./types";

type Row = Record<string, unknown>;
function exact(value: unknown, keys: readonly string[]): Row {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Invalid alert delivery response");
  const row = value as Row; const actual = Object.keys(row).sort(); const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) throw new Error("Invalid alert delivery response");
  return row;
}
function timestamp(value: unknown, nullable = false): value is string | null {
  return (nullable && value === null) || (typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value)) && /(?:Z|[+-]\d{2}:\d{2})$/.test(value));
}
function count(value: unknown): value is number { return typeof value === "number" && Number.isSafeInteger(value) && value >= 0; }
function reason(value: unknown): value is string | null { return value === null || (typeof value === "string" && /^[a-z_]{1,64}$/.test(value)); }
const phases = new Set(["send_started", "accepted", "retry_wait", "failed", "delivery_unknown", "claim_recovered"]);
const states = new Set(["pending", "claimed", "accepted", "retry_wait", "failed", "delivery_unknown", "cancelled", "superseded"]);
function attempt(value: unknown): AlertDeliveryAttempt {
  const row = exact(value, ["attempt_number", "phase", "safe_reason", "occurred_at"]);
  if (!count(row.attempt_number) || typeof row.phase !== "string" || !phases.has(row.phase) || !reason(row.safe_reason) || !timestamp(row.occurred_at)) throw new Error("Invalid alert delivery response");
  return row as unknown as AlertDeliveryAttempt;
}
function delivery(value: unknown): AlertDelivery {
  const row = exact(value, ["outbox_id", "species_code", "sequence", "method", "state", "attempt_count", "next_attempt_at", "updated_at", "terminal_at", "safe_terminal_reason", "allowed_actions", "can_retry", "attempts"]);
  if (typeof row.outbox_id !== "string" || !/^alert_outbox_[A-Za-z0-9_-]{1,100}$/.test(row.outbox_id)
    || typeof row.species_code !== "string" || !/^[A-Za-z0-9]{1,64}$/.test(row.species_code)
    || !count(row.sequence) || (row.method !== "REQUEST" && row.method !== "CANCEL")
    || typeof row.state !== "string" || !states.has(row.state) || !count(row.attempt_count)
    || !timestamp(row.next_attempt_at) || !timestamp(row.updated_at) || !timestamp(row.terminal_at, true)
    || !reason(row.safe_terminal_reason) || !Array.isArray(row.allowed_actions)
    || row.allowed_actions.length > 2 || new Set(row.allowed_actions).size !== row.allowed_actions.length
    || row.allowed_actions.some((action) => !["mark_delivered", "mark_not_delivered", "mark_not_delivered_and_retry", "retry_failed"].includes(String(action)))
    || typeof row.can_retry !== "boolean"
    || row.can_retry !== row.allowed_actions.some((action) => action === "mark_not_delivered_and_retry" || action === "retry_failed")
    || !Array.isArray(row.attempts) || row.attempts.length > 20) {
    throw new Error("Invalid alert delivery response");
  }
  const expectedActions = row.state === "delivery_unknown"
    ? row.can_retry ? ["mark_delivered", "mark_not_delivered_and_retry"] : ["mark_delivered", "mark_not_delivered"]
    : row.state === "failed" && row.can_retry ? ["retry_failed"] : [];
  if (JSON.stringify(row.allowed_actions) !== JSON.stringify(expectedActions)) throw new Error("Invalid alert delivery response");
  return { ...(row as unknown as Omit<AlertDelivery, "attempts">), attempts: row.attempts.map(attempt) };
}
const safeErrors: Record<string, string> = {
  database_unavailable: "Alert delivery status is unavailable.", delivery_busy: "Another alert operation is in progress.",
  invalid_state: "That alert delivery state can no longer be changed.", confirmation_required: "Confirm the alert operation.",
  invalid_request: "The alert delivery request is invalid.",
};
async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, init); let body: unknown;
  try { body = await response.json(); } catch { throw new Error("Alert delivery status is unavailable."); }
  if (!response.ok) {
    try { const outer = exact(body, ["error"]); const error = exact(outer.error, ["code", "message"]); if (typeof error.code === "string" && safeErrors[error.code]) throw new Error(safeErrors[error.code]); }
    catch (cause) { if (cause instanceof Error && cause.message !== "Invalid alert delivery response") throw cause; }
    throw new Error("Alert delivery status is unavailable.");
  }
  return body;
}
export async function listAlertDeliveries(): Promise<AlertDelivery[]> {
  const row = exact(await request("/api/alert-deliveries"), ["deliveries"]);
  if (!Array.isArray(row.deliveries) || row.deliveries.length > 1000) throw new Error("Invalid alert delivery response");
  return row.deliveries.map(delivery);
}
async function action(path: string, expected: "accepted" | "not_delivered" | "retry_enqueued"): Promise<string> {
  const row = exact(await request(path, { method: "POST" }), ["status", "outbox_id"]);
  if (row.status !== expected || typeof row.outbox_id !== "string" || !row.outbox_id.startsWith("alert_outbox_")) throw new Error("Invalid alert delivery response");
  return row.outbox_id;
}
export function markAlertDelivered(id: string): Promise<string> { return action(`/api/alert-deliveries/${encodeURIComponent(id)}/mark-delivered?confirm=true`, "accepted"); }
export function markAlertNotDelivered(id: string): Promise<string> { return action(`/api/alert-deliveries/${encodeURIComponent(id)}/mark-not-delivered?confirm=true`, "not_delivered"); }
export function retryAlertDelivery(id: string): Promise<string> { return action(`/api/alert-deliveries/${encodeURIComponent(id)}/retry?confirm=true`, "retry_enqueued"); }
