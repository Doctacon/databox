const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const ISO_TIMESTAMP = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|([+-])(\d{2}):(\d{2}))?$/;

function validDateParts(year: number, month: number, day: number): boolean {
  if (year < 1 || year > 9999 || month < 1 || month > 12) return false;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day >= 1 && day <= days[month - 1];
}

export function isIsoDate(value: unknown, nullable = false): value is string | null {
  if (nullable && value === null) return true;
  if (typeof value !== "string" || value.length > 10) return false;
  const match = ISO_DATE.exec(value);
  return match !== null && validDateParts(Number(match[1]), Number(match[2]), Number(match[3]));
}

export function isoTimestampMicros(value: unknown, requireOffset = false): bigint | null {
  if (typeof value !== "string" || value.length > 64) return null;
  const match = ISO_TIMESTAMP.exec(value);
  if (!match || (requireOffset && !match[8])) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  const offsetHour = match[10] ? Number(match[10]) : 0;
  const offsetMinute = match[11] ? Number(match[11]) : 0;
  if (!validDateParts(year, month, day) || hour > 23 || minute > 59 || second > 59
    || offsetHour > 14 || offsetMinute > 59 || (offsetHour === 14 && offsetMinute !== 0)) return null;
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  date.setUTCHours(hour, minute, second, 0);
  let micros = BigInt(date.getTime()) * 1000n + BigInt((match[7] || "").padEnd(6, "0"));
  if (match[9]) {
    const offset = BigInt(offsetHour * 60 + offsetMinute) * 60_000_000n;
    micros += match[9] === "+" ? -offset : offset;
  }
  return micros;
}

export function isIsoTimestamp(value: unknown, nullable = false, requireOffset = false): value is string | null {
  return (nullable && value === null) || isoTimestampMicros(value, requireOffset) !== null;
}
