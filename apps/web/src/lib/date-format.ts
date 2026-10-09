const API_DATE_TIME_RE = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?([zZ]|[+-]\d{2}:?\d{2})?$/

// Existing SQLite/API datetimes are offset-free UTC, never browser-local time.
export function parseApiTimestamp(value: string | null | undefined): Date | null {
  const match = value?.match(API_DATE_TIME_RE)
  if (!match) return null
  const [, year, month, day, hour, minute, second = "00", fraction, offset = "Z"] = match
  const y = Number(year), m = Number(month), d = Number(day)
  const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0)
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  if (y < 1 || m < 1 || m > 12 || d < 1 || d > days[m - 1] || Number(hour) > 23 || Number(minute) > 59 || Number(second) > 59) return null
  const zone = /^[zZ]$/.test(offset) ? "Z" : offset.replace(/([+-]\d{2})(\d{2})$/, "$1:$2")
  if (zone !== "Z" && (Number(zone.slice(1, 3)) > 23 || Number(zone.slice(4)) > 59)) return null
  // JS displays milliseconds; preserve the exact API value in timestamp titles.
  const milliseconds = fraction ? `.${fraction.slice(0, 3).padEnd(3, "0")}` : ""
  const date = new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}${milliseconds}${zone}`)
  return Number.isFinite(date.getTime()) ? date : null
}

export function apiTimestampEpoch(value: string | null | undefined): number {
  return parseApiTimestamp(value)?.getTime() ?? NaN
}

export function compareApiTimestamps(left: string | null | undefined, right: string | null | undefined): number {
  const a = parseApiTimestamp(left)?.getTime() ?? -Infinity
  const b = parseApiTimestamp(right)?.getTime() ?? -Infinity
  return a === b ? 0 : a > b ? 1 : -1
}

function dateParts(date: Date, timeZone: string) {
  const options: Intl.DateTimeFormatOptions = { timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZoneName: "longOffset" }
  let formatter: Intl.DateTimeFormat
  try { formatter = new Intl.DateTimeFormat("zh-CN", options) }
  catch { formatter = new Intl.DateTimeFormat("zh-CN", { ...options, timeZone: "UTC" }) }
  return { zone: formatter.resolvedOptions().timeZone, parts: Object.fromEntries(formatter.formatToParts(date).map(part => [part.type, part.value])) }
}

// Explicit UTC default keeps server rendering deterministic across host zones.
export function formatCompactDateTime(value: string, timeZone = "UTC"): string {
  const date = parseApiTimestamp(value)
  if (!date) return value
  const { parts } = dateParts(date, timeZone)
  return `${Number(parts.month)}月${Number(parts.day)}日 ${parts.hour}:${parts.minute}`
}

export function timestampDetails(value: string, timeZone = "UTC"): string {
  const date = parseApiTimestamp(value)
  if (!date) return `无法解析时间 · 原始值：${value}`
  const { parts, zone } = dateParts(date, timeZone)
  const offsetName = parts.timeZoneName.replace("GMT", "UTC")
  // Node and browsers can label zero-offset longOffset as GMT or GMT+00:00.
  const offset = /^UTC(?:[+-]00(?::00)?)?$/.test(offsetName) ? "UTC+00:00" : offsetName
  return `显示时间：${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}\n时区：${zone}（${offset}）\nUTC：${date.toISOString()}\n原始值：${value}`
}
