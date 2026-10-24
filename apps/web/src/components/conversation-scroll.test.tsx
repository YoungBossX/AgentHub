import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import type { ChatMessage } from "@/lib/api"
import { ConversationScroll } from "./conversation-scroll"

let height = 800
let resize: () => void
const message = (id: string, contentMd = id) => ({ id, contentMd } as ChatMessage)
beforeEach(() => {
  height = 800
  vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(() => height)
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(300)
  vi.stubGlobal("ResizeObserver", class { constructor(callback: () => void) { resize = callback } observe() {} disconnect() {} })
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => { callback(0); return 1 })
  vi.stubGlobal("cancelAnimationFrame", vi.fn())
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
const panel = (messages: ChatMessage[], sessionId = "a", historical = false, active = true) => <ConversationScroll sessionId={sessionId} active={active} historical={historical} loading={false} messages={messages}><p>会话内容</p></ConversationScroll>
const scroller = () => document.querySelector('[data-region="center-scroll"]')! as HTMLDivElement

it("follows appends near the bottom but preserves reading above it with a deduplicated notice", () => {
  const view = render(panel([message("1")]))
  expect(scroller().scrollTop).toBe(500)
  height = 1000
  view.rerender(panel([message("1"), message("2")]))
  expect(scroller().scrollTop).toBe(700)
  scroller().scrollTop = 100
  fireEvent.scroll(scroller())
  height = 1200
  view.rerender(panel([message("1"), message("2"), message("3")]))
  expect(scroller().scrollTop).toBe(100)
  expect(screen.getByRole("button", { name: /1 条新消息/ })).toBeTruthy()
  view.rerender(panel([message("1"), message("2"), message("3", "连续中文输出")]))
  expect(screen.getByRole("button", { name: /1 条新消息/ })).toBeTruthy()
  act(() => resize())
  expect(scroller().scrollTop).toBe(100)
  fireEvent.click(screen.getByRole("button", { name: /跳至最新/ }))
  expect(scroller().scrollTop).toBe(900)
  expect(screen.queryByRole("button", { name: /跳至最新/ })).toBeNull()
})
it("does not move historical pages, resumes on explicit latest, and clears session notifications", () => {
  const view = render(panel([message("1")]))
  scroller().scrollTop = 80
  fireEvent.scroll(scroller())
  view.rerender(panel([message("old"), message("1")], "a", true))
  expect(scroller().scrollTop).toBe(80)
  expect(screen.queryByRole("button", { name: /跳至最新/ })).toBeNull()
  view.rerender(panel([message("2")], "a", false))
  expect(scroller().scrollTop).toBe(500)
  scroller().scrollTop = 20
  fireEvent.scroll(scroller())
  view.rerender(panel([message("2"), message("3")]))
  expect(screen.getByRole("button", { name: /1 条新消息/ })).toBeTruthy()
  view.rerender(panel([message("b1")], "b"))
  expect(screen.queryByRole("button", { name: /跳至最新/ })).toBeNull()
  expect(scroller().scrollTop).toBe(500)
})
it("offers new-content feedback for same-message output and preserves position across views", () => {
  const view = render(panel([message("1")]))
  scroller().scrollTop = 80
  fireEvent.scroll(scroller())
  view.rerender(panel([message("1", "追加内容")]))
  expect(screen.getByRole("button", { name: /有新内容/ })).toBeTruthy()
  view.rerender(panel([message("1", "追加内容")], "a", false, false))
  scroller().scrollTop = 350
  fireEvent.scroll(scroller())
  view.rerender(panel([message("1", "追加内容")]))
  expect(scroller().scrollTop).toBe(80)
})

it.each([40, 41])("only follows unpaused output within 40px, distance %s", distance => {
  const view = render(panel([message("1")]))
  scroller().scrollTop = 500 - distance
  fireEvent.scroll(scroller())
  height = 1000
  view.rerender(panel([message("1"), message("2")]))
  expect(scroller().scrollTop).toBe(distance <= 40 ? 700 : 500 - distance)
})

it("offers jump beyond 120px even when no new messages arrive", () => {
  render(panel([message("1")]))
  scroller().scrollTop = 380
  fireEvent.scroll(scroller())
  expect(screen.queryByRole("button", { name: /跳至最新/ })).toBeNull()
  scroller().scrollTop = 379
  fireEvent.scroll(scroller())
  fireEvent.click(screen.getByRole("button", { name: "跳至最新" }))
  expect(scroller().scrollTop).toBe(500)
})

it.each(["wheel", "touchMove", "keyDown"])("pauses on %s before scroll events, resumes only at actual bottom", gesture => {
  const view = render(panel([message("1")]))
  if (gesture === "wheel") fireEvent.wheel(scroller(), { deltaY: -10 })
  else if (gesture === "touchMove") fireEvent.touchMove(scroller())
  else fireEvent.keyDown(scroller(), { key: "ArrowUp" })
  scroller().scrollTop = 490
  fireEvent.scroll(scroller())
  height = 1000
  view.rerender(panel([message("1"), message("2")]))
  expect(scroller().scrollTop).toBe(490)
  scroller().scrollTop = 700
  fireEvent.scroll(scroller())
  height = 1200
  view.rerender(panel([message("1"), message("2"), message("3")]))
  expect(scroller().scrollTop).toBe(900)
})
