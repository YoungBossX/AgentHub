import { describe, expect, it } from "vitest"

import { apiTimestampEpoch, compareApiTimestamps, formatCompactDateTime, parseApiTimestamp, timestampDetails } from "./date-format"

describe("formatCompactDateTime", () => {
  it("defaults to explicit UTC including offset-free microseconds", () => {
    expect(formatCompactDateTime("2026-05-17T02:06:51.123456")).toBe(
      "5月17日 02:06",
    )
    expect(formatCompactDateTime("2026-05-15T10:30:00Z")).toBe(
      "5月15日 10:30",
    )
  })

  it("returns unknown timestamp shapes unchanged", () => {
    expect(formatCompactDateTime("pending")).toBe("pending")
  })

  it("converts equivalent naive, Z and offset representations to the same instant", () => {
    const values = ["2026-10-08T05:25:18.739767", "2026-10-08T05:25:18.739767Z", "2026-10-08 13:25:18.739767+08:00", "2026-10-08T13:25:18.739+0800"]
    expect(values.map(value => apiTimestampEpoch(value))).toEqual(values.map(() => Date.parse("2026-10-08T05:25:18.739Z")))
    expect(compareApiTimestamps(values[0], values[2])).toBe(0)
    expect(compareApiTimestamps("2026-10-08T12:00:00+08:00", "2026-10-08T05:00:00Z")).toBe(-1)
    expect(compareApiTimestamps(null, "2026-10-08T05:00:00Z")).toBe(-1)
    expect(compareApiTimestamps("bad", null)).toBe(0)
  })

  it("handles local midnight and year boundaries without using the host timezone", () => {
    expect(formatCompactDateTime("2026-12-31T20:30:00", "Asia/Shanghai")).toBe("1月1日 04:30")
    expect(formatCompactDateTime("2026-01-01T02:30:00Z", "America/New_York")).toBe("12月31日 21:30")
    expect(formatCompactDateTime("2026-01-01T00:00:00Z", "UTC")).toBe("1月1日 00:00")
    expect(formatCompactDateTime("2024-02-29T23:30:00Z", "Asia/Shanghai")).toBe("3月1日 07:30")
  })

  it("uses the offset at the actual instant across DST changes", () => {
    expect(formatCompactDateTime("2026-03-08T06:59:00Z", "America/New_York")).toBe("3月8日 01:59")
    expect(formatCompactDateTime("2026-03-08T07:00:00Z", "America/New_York")).toBe("3月8日 03:00")
    expect(timestampDetails("2026-11-01T05:30:00Z", "America/New_York")).toContain("UTC-04:00")
    expect(timestampDetails("2026-11-01T06:30:00Z", "America/New_York")).toContain("UTC-05:00")
  })

  it("keeps exact raw precision and both local and UTC forms inspectable", () => {
    const raw = "2026-10-08T05:25:18.739767"
    const details = timestampDetails(raw, "Asia/Shanghai")
    expect(details).toContain("2026-10-08 13:25:18")
    expect(details).toContain("Asia/Shanghai（UTC+08:00）")
    expect(details).toContain("UTC：2026-10-08T05:25:18.739Z")
    expect(details).toContain(`原始值：${raw}`)
  })

  it("falls back to explicit UTC for unsupported timezone names", () => {
    expect(formatCompactDateTime("2026-10-08T05:25:18", "invalid-zone")).toBe("10月8日 05:25")
    expect(timestampDetails("2026-10-08T05:25:18", "invalid-zone")).toContain("时区：UTC")
    expect(timestampDetails("2026-10-08T05:25:18", "UTC")).toContain("时区：UTC（UTC+00:00）")
  })

  it.each(["2026-02-29T00:00:00", "2026-02-30T00:00:00Z", "2026-04-31T00:00:00Z", "2026-13-01T00:00:00Z", "2026-00-01T00:00:00Z", "2026-01-00T00:00:00Z", "2026-01-01T24:00:00Z", "2026-01-01T23:60:00Z", "2026-01-01T23:59:60Z", "2026-01-01T00:00:00+24:00", "2026-01-01T00:00:00+01:60", "2026-01-01", "pending", "2026-01-01T00:00:00Zjunk"])("rejects invalid instants instead of normalizing %s", value => {
    expect(parseApiTimestamp(value)).toBeNull()
    expect(Number.isNaN(apiTimestampEpoch(value))).toBe(true)
    expect(formatCompactDateTime(value, "Asia/Shanghai")).toBe(value)
  })
})
