import { afterEach, expect, it, vi } from "vitest";
import { listAlertDeliveries, markAlertDelivered, markAlertNotDelivered, retryAlertDelivery } from "./alertDeliveryApi";
function response(body: unknown, status = 200) { return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })); }
const delivery = {
  outbox_id: `alert_outbox_${"a".repeat(64)}`, species_code: "target1", sequence: 1,
  method: "REQUEST", state: "delivery_unknown", attempt_count: 1,
  next_attempt_at: "2026-07-10T12:00:00+00:00", updated_at: "2026-07-10T12:00:00+00:00",
  terminal_at: null, safe_terminal_reason: "smtp_acceptance_ambiguous",
  allowed_actions: ["mark_delivered", "mark_not_delivered_and_retry"], can_retry: true,
  attempts: [{ attempt_number: 1, phase: "delivery_unknown", safe_reason: "smtp_acceptance_ambiguous", occurred_at: "2026-07-10T12:00:00+00:00" }],
};
afterEach(() => vi.restoreAllMocks());
it("validates bounded delivery status and rejects private or malformed fields", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({ deliveries: [delivery] }));
  expect(await listAlertDeliveries()).toEqual([delivery]);
  vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({ deliveries: [{ ...delivery, recipient: "secret@example.invalid" }] }));
  await expect(listAlertDeliveries()).rejects.toThrow("Invalid alert delivery response");
  vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({ deliveries: [{ ...delivery, attempt_count: 1.5 }] }));
  await expect(listAlertDeliveries()).rejects.toThrow("Invalid alert delivery response");
  vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({ deliveries: [{ ...delivery, can_retry: false }] }));
  await expect(listAlertDeliveries()).rejects.toThrow("Invalid alert delivery response");
});
it("uses confirmed safe reconciliation endpoints and suppresses server details", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockImplementationOnce(() => response({ status: "accepted", outbox_id: delivery.outbox_id }))
    .mockImplementationOnce(() => response({ status: "not_delivered", outbox_id: delivery.outbox_id }))
    .mockImplementationOnce(() => response({ status: "retry_enqueued", outbox_id: `alert_outbox_${"b".repeat(64)}` }))
    .mockImplementationOnce(() => response({ error: { code: "database_unavailable", message: "/private/db secret" } }, 503));
  await expect(markAlertDelivered(delivery.outbox_id)).resolves.toBe(delivery.outbox_id);
  await expect(markAlertNotDelivered(delivery.outbox_id)).resolves.toBe(delivery.outbox_id);
  await expect(retryAlertDelivery(delivery.outbox_id)).resolves.toMatch(/^alert_outbox_/);
  await expect(listAlertDeliveries()).rejects.toThrow("Alert delivery status is unavailable.");
  expect(fetchMock.mock.calls[0][0]).toContain("confirm=true");
  expect(fetchMock.mock.calls[1][0]).toContain("mark-not-delivered?confirm=true");
  expect(fetchMock.mock.calls[2][0]).toContain("confirm=true");
});
