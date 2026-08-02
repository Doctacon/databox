import { useState } from "react";
import { downloadPublishedCalendar } from "../publicCalendar";
import type { TripCalendarInviteStatus } from "../types";
import { getPlan } from "./tripApi";

function escapeIcs(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/\r?\n/g, "\\n").replace(/,/g, "\\,").replace(/;/g, "\\;");
}

function calendarTimestamp(value: string | Date): string {
  return new Date(value).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function foldLine(line: string): string[] {
  const encoder = new TextEncoder();
  const result: string[] = [];
  let current = "";
  for (const character of line) {
    if (encoder.encode(current + character).length > 75 && current) {
      result.push(current);
      current = ` ${character}`;
    } else current += character;
  }
  result.push(current);
  return result;
}

export function TripCalendarControls({
  planId,
  invite: _invite,
  onChange: _onChange,
}: {
  planId: string;
  invite: TripCalendarInviteStatus;
  onChange: (invite: TripCalendarInviteStatus) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    if (busy) return;
    setBusy(true); setMessage(null); setError(null);
    try {
      const detail = await getPlan(planId);
      const name = detail.plan.normalized_location_name || detail.plan.requested_location;
      const description = [detail.plan.field_plan_text, ...detail.plan.caveats].filter(Boolean).join("\n\n");
      const lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Lough on Data//Rufous//EN",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        `UID:${escapeIcs(planId)}@rufous.loughondata.com`,
        `DTSTAMP:${calendarTimestamp(new Date())}`,
        `DTSTART:${calendarTimestamp(detail.plan.window_start)}`,
        `DTEND:${calendarTimestamp(detail.plan.window_end)}`,
        `SUMMARY:${escapeIcs(`Birding outing at ${name}`)}`,
        `LOCATION:${escapeIcs(name)}`,
        ...(detail.plan.latitude !== null && detail.plan.longitude !== null
          ? [`GEO:${detail.plan.latitude};${detail.plan.longitude}`]
          : []),
        `DESCRIPTION:${escapeIcs(description)}`,
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR",
      ];
      downloadPublishedCalendar(
        `rufous-${name.toLocaleLowerCase().replace(/[^a-z0-9]+/g, "-")}.ics`,
        `${lines.flatMap(foldLine).join("\r\n")}\r\n`,
      );
      setMessage("Calendar file downloaded. Rufous did not collect an email address or send a message.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The calendar file could not be created.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel" aria-labelledby="calendar-invite-heading" aria-busy={busy}>
    <h2 id="calendar-invite-heading">Calendar event</h2>
    <p className="source-status">Built and downloaded entirely in your browser. No email server is involved.</p>
    <div className="button-row"><button type="button" disabled={busy} onClick={() => void download()}>
      {busy ? "Building calendar file…" : "Download calendar event (.ics)"}
    </button></div>
    {message && <p className="success" role="status">{message}</p>}
    {error && <p className="error" role="alert">{error}</p>}
  </section>;
}
