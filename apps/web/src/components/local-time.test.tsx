import { act, cleanup, render, screen } from "@testing-library/react"
import { hydrateRoot, type Root } from "react-dom/client"
import { renderToString } from "react-dom/server"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { LocalTime, TimeZoneLabel } from "./local-time"

const originalZone = process.env.TZ
beforeEach(() => { process.env.TZ = "Asia/Shanghai" })
afterEach(() => {
  cleanup()
  if (originalZone === undefined) delete process.env.TZ
  else process.env.TZ = originalZone
})

describe("local timestamps", () => {
  it("renders local time with normalized datetime and exact source details", () => {
    const raw = "2026-10-08T05:25:18.739767"
    const { container } = render(<><TimeZoneLabel /><LocalTime value={raw} /></>)
    expect(screen.getByText("10月8日 13:25")).toBeTruthy()
    expect(screen.getByText("本地时间 · Asia/Shanghai")).toBeTruthy()
    const time = container.querySelector("time")!
    expect(time.dateTime).toBe("2026-10-08T05:25:18.739Z")
    expect(time.title).toContain(`原始值：${raw}`)
    expect(time.title).toContain("UTC+08:00")
  })

  it("does not invent datetime values for missing or invalid timestamps", () => {
    const { container } = render(<><LocalTime value={null} emptyLabel="暂无消息" /><LocalTime value="2026-02-30T00:00:00" /></>)
    expect(screen.getByText("暂无消息")).toBeTruthy()
    expect(screen.getByText("2026-02-30T00:00:00").title).toContain("无法解析时间")
    expect(container.querySelector("time")).toBeNull()
  })

  it("hydrates UTC server output in a local browser without mismatches", async () => {
    const node = <><TimeZoneLabel /><LocalTime value="2026-12-31T20:30:00" /></>
    const container = document.createElement("div")
    container.innerHTML = renderToString(node)
    expect(container.textContent).toContain("时间 · UTC")
    expect(container.textContent).toContain("12月31日 20:30")
    document.body.append(container)
    const errors: unknown[] = []
    let root!: Root
    try {
      await act(async () => { root = hydrateRoot(container, node, { onRecoverableError: error => errors.push(error) }) })
      expect(container.textContent).toContain("本地时间 · Asia/Shanghai")
      expect(container.textContent).toContain("1月1日 04:30")
      expect(errors).toEqual([])
    } finally {
      await act(async () => root?.unmount())
      container.remove()
    }
  })
})
