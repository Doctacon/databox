import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TripCalendarControls } from "./TripCalendarControls";
import type { TripCalendarInviteStatus } from "./types";
import * as api from "./api";

const outbox = `trip_outbox_${"a".repeat(64)}`;
const notCreated: TripCalendarInviteStatus = {
  status: "not_created", sequence: null, outbox_id: null, allowed_actions: ["send"],
  can_retry: false, updated_at: null, acceptance_notice: null,
};
function state(status: "accepted" | "failed" | "delivery_unknown" | "pending"): TripCalendarInviteStatus {
  return {
    status, sequence: 0, outbox_id: outbox,
    allowed_actions: status === "accepted" ? ["send_update"] : status === "failed" ? ["retry_failed"]
      : status === "delivery_unknown" ? ["mark_delivered", "mark_not_delivered_and_retry"] : [],
    can_retry: status === "failed", updated_at: "2026-07-10T12:00:00Z",
    acceptance_notice: status === "accepted" ? "Accepted by local mail bridge" : null,
  };
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("persisted trip calendar controls", () => {
  it("requires confirmation for first send, reports local-Bridge acceptance, and prevents concurrent duplicates", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValue(true);
    let resolve!: (value: TripCalendarInviteStatus) => void;
    const action = vi.spyOn(api, "actOnTripCalendarInvite").mockReturnValue(new Promise((done) => { resolve = done; }));
    const onChange = vi.fn();
    render(<TripCalendarControls planId="trip_fixture" invite={notCreated} onChange={onChange} />);
    const send = screen.getByRole("button", { name: "Send calendar invite" });
    await user.click(send);
    expect(action).not.toHaveBeenCalled();
    await user.dblClick(send);
    expect(action).toHaveBeenCalledTimes(1);
    expect(send).toBeDisabled();
    resolve(state("accepted"));
    expect(await screen.findByText("Accepted by local mail bridge. Inbox or calendar delivery is not confirmed.")).toHaveFocus();
    expect(onChange).toHaveBeenCalledWith(state("accepted"));
  });

  it.each([
    [state("accepted"), "Update calendar invite", "send_update"],
    [state("failed"), "Retry calendar invite", "retry_failed"],
    [state("delivery_unknown"), "Reconcile as accepted by local Bridge", "mark_delivered"],
    [state("delivery_unknown"), "Reconcile as not delivered and retry", "mark_not_delivered_and_retry"],
  ] as const)("renders only server-allowed explicit action for %s", async (invite, label, expectedAction) => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "actOnTripCalendarInvite").mockResolvedValue(state("accepted"));
    render(<TripCalendarControls planId="trip_fixture" invite={invite} onChange={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: label }));
    expect(api.actOnTripCalendarInvite).toHaveBeenCalledWith("trip_fixture", invite, expectedAction);
  });

  it("renders persisted pending status on reload without an implicit send", () => {
    const action = vi.spyOn(api, "actOnTripCalendarInvite");
    render(<TripCalendarControls planId="trip_fixture" invite={state("pending")} onChange={vi.fn()} />);
    expect(screen.getByText(/processing is in progress/)).toBeVisible();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(action).not.toHaveBeenCalled();
  });

  it("shows a fixed action error with alert focus and no transport data", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "actOnTripCalendarInvite").mockRejectedValue(new Error("The calendar invitation state changed. Reload the plan and try again."));
    render(<TripCalendarControls planId="trip_fixture" invite={state("failed")} onChange={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Retry calendar invite" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveFocus();
    expect(alert).not.toHaveTextContent(/smtp|recipient|payload|config/i);
  });
});
