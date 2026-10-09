import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { COLUMN_STORAGE_KEY, WorkbenchLayout } from "./workbench-layout"

let containerWidth = 1400
class TestPointerEvent extends MouseEvent {
  pointerId: number
  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init)
    this.pointerId = init.pointerId ?? 1
  }
}

beforeEach(() => {
  containerWidth = 1400
  vi.stubGlobal("PointerEvent", TestPointerEvent)
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(() => ({ x: 0, y: 0, top: 0, left: 0, right: containerWidth, bottom: 900, width: containerWidth, height: 900, toJSON: () => ({}) }))
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})

const layout = (collapsed = false, expanded = false) => <WorkbenchLayout className="workbench-layout" inspectorCollapsed={collapsed} inspectorExpanded={expanded}><div>会话</div><main>对话</main><aside>成果</aside></WorkbenchLayout>
const separator = (side: "sidebar" | "inspector") => screen.getByRole("separator", { name: side === "sidebar" ? "调整会话侧栏宽度" : "调整成果面板宽度" })
const value = (side: "sidebar" | "inspector") => Number(separator(side).getAttribute("aria-valuenow"))
const pointer = (x: number, pointerId = 1) => ({ clientX: x, pointerId, button: 0 })

describe("resizable workbench", () => {
  it("drags each boundary independently and persists only finished drags", () => {
    const { container } = render(layout())
    fireEvent.pointerDown(separator("sidebar"), pointer(220))
    expect(container.querySelector(".workbench-drag-shield")).toBeTruthy()
    fireEvent.pointerMove(separator("sidebar"), pointer(500, 2))
    expect(value("sidebar")).toBe(220)
    fireEvent.pointerMove(separator("sidebar"), pointer(310))
    expect(value("sidebar")).toBe(310)
    expect(value("inspector")).toBe(360)
    expect(localStorage.getItem(COLUMN_STORAGE_KEY)).toBeNull()
    fireEvent.pointerUp(separator("sidebar"), pointer(310))
    expect(container.querySelector(".workbench-drag-shield")).toBeNull()
    fireEvent.pointerDown(separator("inspector"), pointer(1040))
    fireEvent.pointerMove(separator("inspector"), pointer(940))
    fireEvent.pointerUp(separator("inspector"), pointer(940))
    expect(value("inspector")).toBe(460)
    expect(value("sidebar")).toBe(310)
    expect(JSON.parse(localStorage.getItem(COLUMN_STORAGE_KEY)!)).toEqual({ sidebar: 310, inspector: 460 })
  })

  it.each(["pointercancel", "Escape", "blur"])("cleans up and restores widths after %s", (cancel) => {
    const { container } = render(layout())
    fireEvent.pointerDown(separator("sidebar"), pointer(220))
    fireEvent.pointerMove(separator("sidebar"), pointer(300))
    if (cancel === "Escape") fireEvent.keyDown(separator("sidebar"), { key: "Escape" })
    else if (cancel === "blur") fireEvent.blur(window)
    else fireEvent.pointerCancel(separator("sidebar"), pointer(300))
    expect(value("sidebar")).toBe(220)
    expect(container.querySelector(".workbench-drag-shield")).toBeNull()
    expect(localStorage.getItem(COLUMN_STORAGE_KEY)).toBeNull()
  })

  it("bounds pointer and keyboard resizing to leave at least 400px in the center", () => {
    render(layout())
    fireEvent.pointerDown(separator("sidebar"), pointer(220))
    fireEvent.pointerMove(separator("sidebar"), pointer(2000))
    fireEvent.pointerUp(separator("sidebar"), pointer(2000))
    expect(value("sidebar")).toBe(360)
    fireEvent.keyDown(separator("inspector"), { key: "End" })
    expect(value("inspector")).toBe(640)
    expect(containerWidth - value("sidebar") - value("inspector")).toBe(400)
    fireEvent.keyDown(separator("inspector"), { key: "Home" })
    expect(value("inspector")).toBe(280)
    fireEvent.keyDown(separator("inspector"), { key: "ArrowLeft" })
    expect(value("inspector")).toBe(296)
    fireEvent.keyDown(separator("sidebar"), { key: "Home" })
    expect(value("sidebar")).toBe(180)
  })

  it("restores saved widths, fits smaller containers and cancels a drag on narrow layouts", () => {
    localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify({ sidebar: 320, inspector: 650 }))
    containerWidth = 2000
    const { container } = render(layout())
    expect(value("inspector")).toBe(650)
    containerWidth = 1200
    fireEvent.resize(window)
    expect(value("sidebar")).toBe(320)
    expect(value("inspector")).toBe(480)
    fireEvent.pointerDown(separator("sidebar"), pointer(320))
    fireEvent.pointerMove(separator("sidebar"), pointer(300))
    containerWidth = 390
    fireEvent.resize(window)
    expect(container.querySelector(".workbench-drag-shield")).toBeNull()
    expect((container.firstChild as HTMLElement).style.getPropertyValue("--sidebar-width")).toBe("")
    containerWidth = 2000
    fireEvent.resize(window)
    expect(value("sidebar")).toBe(320)
    expect(value("inspector")).toBe(650)
  })

  it("ignores malformed saved preferences and stays usable when storage is denied", () => {
    localStorage.setItem(COLUMN_STORAGE_KEY, '{"sidebar":9999,"inspector":"bad"}')
    const { unmount } = render(layout())
    expect(value("sidebar")).toBe(220)
    unmount()
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied") })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied") })
    render(layout())
    fireEvent.keyDown(separator("sidebar"), { key: "ArrowRight" })
    expect(value("sidebar")).toBe(236)
  })

  it("resets just the selected pane and preserves preferences across inspector modes", () => {
    containerWidth = 1800
    const { rerender } = render(layout())
    fireEvent.keyDown(separator("sidebar"), { key: "ArrowRight" })
    fireEvent.keyDown(separator("inspector"), { key: "ArrowLeft" })
    fireEvent.doubleClick(separator("sidebar"))
    expect(value("sidebar")).toBe(240)
    expect(value("inspector")).toBe(436)
    rerender(layout(true))
    expect(screen.queryByRole("separator", { name: "调整成果面板宽度" })).toBeNull()
    rerender(layout(false, true))
    expect(screen.queryByRole("separator")).toBeNull()
    rerender(layout())
    expect(value("inspector")).toBe(436)
    expect(screen.getByText("成果")).toBeTruthy()
  })
})
