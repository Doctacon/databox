import { describe, expect, it } from "vitest";
import { isIsoDate, isIsoTimestamp, isoTimestampMicros } from "./isoDateTime";

describe("strict ISO date and timestamp validation", () => {
  it.each([
    "2026-02-29", "2024-02-30", "2026-04-31", "0000-01-01", "2026-00-01", "2026-01-00",
    "0", "2026/01/01", "2026-1-01", "2026-01-01T00:00:00",
  ])("rejects invalid ISO date %s", (value) => expect(isIsoDate(value)).toBe(false));

  it.each(["2024-02-29", "2026-04-30", "9999-12-31", "0001-01-01"])(
    "accepts valid ISO date %s", (value) => expect(isIsoDate(value)).toBe(true),
  );

  it.each([
    "2026-02-29T06:00:00", "2024-02-30T06:00:00", "2026-04-31T06:00:00",
    "2026-01-01T24:00:00", "2026-01-01T06:60:00", "2026-01-01T06:00:60",
    "2026-01-01T06:00:00+24:00", "2026-01-01T06:00:00+14:01",
    "0000-01-01T06:00:00", "0", "2026-01-01", "2026-01-01 06:00:00",
  ])("rejects invalid ISO timestamp %s", (value) => expect(isIsoTimestamp(value)).toBe(false));

  it.each([
    "2024-02-29T06:00:00", "2026-01-01T06:00:00Z", "2026-01-01T06:00:00.123456+00:00",
    "2026-01-01T06:00:00-07:00", "2026-01-01T06:00:00+14:00",
  ])("accepts valid backend timestamp %s", (value) => expect(isIsoTimestamp(value)).toBe(true));

  it("enforces offset-required fields and nullable contracts", () => {
    expect(isIsoTimestamp("2026-01-01T06:00:00", false, true)).toBe(false);
    expect(isIsoTimestamp("2026-01-01T06:00:00Z", false, true)).toBe(true);
    expect(isIsoTimestamp(null, true, true)).toBe(true);
    expect(isIsoDate(null, true)).toBe(true);
    expect(isIsoTimestamp(0)).toBe(false);
    expect(isIsoDate(Number.NaN)).toBe(false);
  });

  it("normalizes valid offsets for exact duration comparisons", () => {
    expect(isoTimestampMicros("2026-01-01T06:00:00-07:00")).toBe(
      isoTimestampMicros("2026-01-01T13:00:00Z"),
    );
  });
});
