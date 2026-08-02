import { describe, expect, it } from "vitest";
import { buildPublishedCalendar, formatOccurrenceDate, minimumOutingDate, sunriseUtc, sunriseWindow } from "./publicCalendar";
import type { PublicWatch, WatchMatch } from "./publicTypes";

const watch: PublicWatch = {
  id: "watch-calendar-fixture",
  species_code: "mexjay",
  bird_name: "Mexican Jay",
  center_name: "Thumb Butte, Arizona",
  center_latitude: 34.5409,
  center_longitude: -112.553,
  center_timezone: "America/Phoenix",
  radius_miles: 25,
  outing_date: "2026-08-02",
  created_at: "2026-08-01T12:00:00Z",
};

const match: WatchMatch = {
  public_id: "synthetic-match",
  species_code: "mexjay",
  observed_at: "2026-07-29T12:20:00Z",
  count: 4,
  count_display: "4 birds",
  is_notable: false,
  source: "synthetic",
  attribution_id: "rufous-fixture",
  location: {
    name: "Granite Trail; North",
    latitude: 34.5431,
    longitude: -112.4902,
    kind: "Public site",
    timezone: "America/Phoenix",
    timezone_source: "fixture",
  },
  distance_miles: 3.6,
};

describe("public sunrise calendar", () => {
  it("requires a future-facing Arizona outing date", () => {
    expect(minimumOutingDate(new Date("2026-08-01T23:30:00Z"))).toBe("2026-08-02");
    expect(minimumOutingDate(new Date("2026-08-02T06:30:00Z"))).toBe("2026-08-02");
  });

  it("calculates a plausible deterministic Arizona sunrise and two-hour window", () => {
    const sunrise = sunriseUtc("2026-08-02", 34.5409, -112.553);
    expect(sunrise.toISOString()).toMatch(/^2026-08-02T12:/);
    const window = sunriseWindow(watch);
    expect(window.sunrise.getTime() - window.start.getTime()).toBe(60 * 60 * 1000);
    expect(window.end.getTime() - window.sunrise.getTime()).toBe(60 * 60 * 1000);
  });

  it("renders a GBIF date-only occurrence without a west-of-UTC day shift", () => {
    expect(formatOccurrenceDate("2024-07-20", "en-US")).toBe("Jul 20, 2024");
  });

  it("publishes a folded client calendar without messaging or RSVP fields", () => {
    const calendar = buildPublishedCalendar(
      watch,
      match,
      "Look near flowering oaks, listen first, and keep a respectful distance. This intentionally long sentence verifies standards-compliant calendar line folding.",
      new Date("2026-08-01T12:00:00Z"),
    );
    expect(calendar).toContain("METHOD:PUBLISH\r\n");
    expect(calendar).toContain("UID:watch-calendar-fixture-2026-08-02@rufous.loughondata.com");
    expect(calendar).toContain("LOCATION:Granite Trail\\; North");
    expect(calendar).toContain("Licensed historical occurrence");
    expect(calendar).not.toContain("Recent public evidence");
    expect(calendar).not.toMatch(/ORGANIZER|ATTENDEE|MAILTO|RSVP|METHOD:REQUEST/i);
    expect(calendar.endsWith("\r\n")).toBe(true);
    for (const line of calendar.split("\r\n").filter(Boolean)) {
      expect(new TextEncoder().encode(line).length).toBeLessThanOrEqual(75);
    }
  });
});
