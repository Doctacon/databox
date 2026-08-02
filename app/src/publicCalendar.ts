import type { PublicWatch, WatchMatch } from "./publicTypes";

const CALENDAR_HOST = "rufous.loughondata.com";

export function minimumOutingDate(now = new Date()): string {
  const tomorrow = new Date(now.getTime() + 86_400_000);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Phoenix",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(tomorrow);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  return `${value("year")}-${value("month")}-${value("day")}`;
}

function normalizeDegrees(value: number): number {
  return ((value % 360) + 360) % 360;
}

function dayOfYear(year: number, month: number, day: number): number {
  return Math.floor((Date.UTC(year, month - 1, day) - Date.UTC(year, 0, 0)) / 86_400_000);
}

export function sunriseUtc(date: string, latitude: number, longitude: number): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) throw new Error("Outing date must use YYYY-MM-DD.");
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const dayNumber = dayOfYear(year, month, day);
  const longitudeHour = longitude / 15;
  const approximateTime = dayNumber + ((6 - longitudeHour) / 24);
  const meanAnomaly = (0.9856 * approximateTime) - 3.289;
  const trueLongitude = normalizeDegrees(
    meanAnomaly
    + (1.916 * Math.sin(meanAnomaly * Math.PI / 180))
    + (0.020 * Math.sin(2 * meanAnomaly * Math.PI / 180))
    + 282.634,
  );
  let rightAscension = normalizeDegrees(Math.atan(0.91764 * Math.tan(trueLongitude * Math.PI / 180)) * 180 / Math.PI);
  rightAscension += Math.floor(trueLongitude / 90) * 90 - Math.floor(rightAscension / 90) * 90;
  rightAscension /= 15;
  const sinDeclination = 0.39782 * Math.sin(trueLongitude * Math.PI / 180);
  const cosDeclination = Math.cos(Math.asin(sinDeclination));
  const cosHour = (
    Math.cos(90.833 * Math.PI / 180)
    - (sinDeclination * Math.sin(latitude * Math.PI / 180))
  ) / (cosDeclination * Math.cos(latitude * Math.PI / 180));
  if (cosHour < -1 || cosHour > 1) throw new Error("Sunrise is unavailable for this location and date.");
  const localHour = (360 - (Math.acos(cosHour) * 180 / Math.PI)) / 15;
  const localMeanTime = localHour + rightAscension - (0.06571 * approximateTime) - 6.622;
  const utcHours = ((localMeanTime - longitudeHour) % 24 + 24) % 24;
  return new Date(Date.UTC(year, month - 1, day) + utcHours * 3_600_000);
}

export function sunriseWindow(watch: PublicWatch): { sunrise: Date; start: Date; end: Date } {
  const sunrise = sunriseUtc(watch.outing_date, watch.center_latitude, watch.center_longitude);
  return {
    sunrise,
    start: new Date(sunrise.getTime() - 60 * 60 * 1000),
    end: new Date(sunrise.getTime() + 60 * 60 * 1000),
  };
}

function escapeIcs(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/\r?\n/g, "\\n").replace(/,/g, "\\,").replace(/;/g, "\\;");
}

function calendarTimestamp(date: Date): string {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

export function formatOccurrenceDate(value: string, locale?: string): string {
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const parsed = new Date(dateOnly ? `${value}T00:00:00Z` : value);
  if (!Number.isFinite(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    ...(dateOnly ? { timeZone: "UTC" } : {}),
  }).format(parsed);
}

function foldLine(line: string): string[] {
  const encoder = new TextEncoder();
  const folded: string[] = [];
  let current = "";
  let limit = 75;
  for (const character of line) {
    if (encoder.encode(current + character).length > limit && current) {
      folded.push(current);
      current = ` ${character}`;
      limit = 75;
    } else {
      current += character;
    }
  }
  folded.push(current);
  return folded;
}

export function buildPublishedCalendar(
  watch: PublicWatch,
  match: WatchMatch,
  guidance: string,
  generatedAt = new Date(),
): string {
  const window = sunriseWindow(watch);
  const description = [
    guidance,
    `Licensed historical occurrence: ${match.count_display} near ${match.location.name} on ${formatOccurrenceDate(match.observed_at, "en-US")}.`,
    `Distance from watch center: ${match.distance_miles.toFixed(1)} miles.`,
    "Historical occurrences do not guarantee current presence. Verify current access before visiting.",
    "Built by Rufous from a sanitized public data snapshot.",
  ].join("\n\n");
  const safeId = watch.id.replace(/[^a-z0-9_-]/gi, "-");
  const lines = [
    "BEGIN:VCALENDAR",
    "PRODID:-//Lough on Data//Rufous//EN",
    "VERSION:2.0",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${safeId}-${watch.outing_date}@${CALENDAR_HOST}`,
    `DTSTAMP:${calendarTimestamp(generatedAt)}`,
    `DTSTART:${calendarTimestamp(window.start)}`,
    `DTEND:${calendarTimestamp(window.end)}`,
    `SUMMARY:${escapeIcs(`Look for ${watch.bird_name}`)}`,
    `LOCATION:${escapeIcs(match.location.name)}`,
    `GEO:${match.location.latitude};${match.location.longitude}`,
    `DESCRIPTION:${escapeIcs(description)}`,
    "STATUS:CONFIRMED",
    "TRANSP:OPAQUE",
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return `${lines.flatMap(foldLine).join("\r\n")}\r\n`;
}

export function downloadPublishedCalendar(filename: string, contents: string): void {
  const blob = new Blob([contents], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename.replace(/[^a-z0-9._-]/gi, "-");
  anchor.rel = "noopener";
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function formatInTimeZone(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(date);
}
