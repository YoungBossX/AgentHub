import { describe, expect, it } from "vitest"

import { formatCompactDateTime } from "./date-format"

describe("formatCompactDateTime", () => {
  it("formats ISO-like timestamps without depending on runtime locale", () => {
    expect(formatCompactDateTime("2026-05-17T02:06:51.123456")).toBe(
      "May 17, 02:06",
    )
    expect(formatCompactDateTime("2026-05-15T10:30:00Z")).toBe(
      "May 15, 10:30",
    )
  })

  it("returns unknown timestamp shapes unchanged", () => {
    expect(formatCompactDateTime("pending")).toBe("pending")
  })
})
