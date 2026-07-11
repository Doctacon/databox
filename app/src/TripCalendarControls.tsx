import { useEffect, useRef, useState } from "react";
import { actOnTripCalendarInvite, type TripCalendarAction } from "./api";
import type { TripCalendarInviteStatus } from "./types";

const labels: Record<TripCalendarAction, string> = {
  send: "Send calendar invite",
  send_update: "Update calendar invite",
  retry_failed: "Retry calendar invite",
  mark_delivered: "Reconcile as accepted by local Bridge",
  mark_not_delivered_and_retry: "Reconcile as not delivered and retry",
};

const confirmations: Record<TripCalendarAction, string> = {
  send: "Send this trip plan to the configured local mail Bridge?",
  send_update: "Send an updated calendar invitation to the configured local mail Bridge?",
  retry_failed: "Retry this failed calendar invitation through the configured local mail Bridge?",
  mark_delivered: "Confirm that the local mail Bridge accepted this calendar invitation?",
  mark_not_delivered_and_retry: "Confirm that the local mail Bridge did not accept this invitation, then retry it?",
};

function statusText(invite: TripCalendarInviteStatus): string {
  if (invite.status === "accepted") return "Accepted by local mail bridge. Inbox or calendar delivery is not confirmed.";
  if (invite.status === "delivery_unknown") return "Local Bridge acceptance is unknown. Reconcile before retrying.";
  if (invite.status === "failed") return "The local Bridge did not accept the calendar invitation.";
  if (["pending", "claimed", "retry_wait"].includes(invite.status)) return "Calendar invitation processing is in progress.";
  if (invite.status === "superseded") return "This calendar invitation attempt was superseded.";
  return "No calendar invitation has been sent.";
}

export function TripCalendarControls({
  planId,
  invite,
  onChange,
}: {
  planId: string;
  invite: TripCalendarInviteStatus;
  onChange: (invite: TripCalendarInviteStatus) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [announcement, setAnnouncement] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busyRef = useRef(false);
  const resultRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (announcement || error) resultRef.current?.focus();
  }, [announcement, error]);

  async function run(action: TripCalendarAction) {
    if (busyRef.current || !window.confirm(confirmations[action])) return;
    busyRef.current = true;
    setBusy(true);
    setAnnouncement("Updating calendar invitation status…");
    setError(null);
    try {
      const next = await actOnTripCalendarInvite(planId, invite, action);
      onChange(next);
      setAnnouncement(statusText(next));
    } catch (reason) {
      setAnnouncement(null);
      setError(reason instanceof Error ? reason.message : "The calendar invitation could not be updated.");
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  return <section className="panel" aria-labelledby="calendar-invite-heading" aria-busy={busy}>
    <h2 id="calendar-invite-heading">Calendar invitation</h2>
    <p className="source-status">{statusText(invite)} Calendar actions only send after confirmation.</p>
    {invite.allowed_actions.length > 0 && <div className="button-row">
      {invite.allowed_actions.map((action) => <button key={action} type="button" disabled={busy} onClick={() => void run(action)}>{labels[action]}</button>)}
    </div>}
    {busy && <p role="status" aria-live="polite">Updating calendar invitation status…</p>}
    {!busy && announcement && <p ref={resultRef} tabIndex={-1} className="success" role="status" aria-live="polite">{announcement}</p>}
    {!busy && error && <p ref={resultRef} tabIndex={-1} className="error" role="alert">{error}</p>}
  </section>;
}
