import { act, renderHook } from "@testing-library/react"
import { expect, it } from "vitest"
import { useInspectorState } from "./use-inspector-state"

it("collapses automatic empty space, reveals selection, and respects manual close across refresh", () => {
  const view = renderHook(({ selected }) => useInspectorState("a", selected), { initialProps: { selected: false } })
  expect(view.result.current.collapsed).toBe(true)
  view.rerender({ selected: true })
  expect(view.result.current.collapsed).toBe(false)
  act(() => view.result.current.close())
  view.rerender({ selected: true })
  expect(view.result.current.collapsed).toBe(true)
  act(() => view.result.current.reveal())
  expect(view.result.current.collapsed).toBe(false)
  expect(view.result.current.overlay).toBe(true)
})
it("isolates manual preference and expansion by session without losing the first session's choice", () => {
  const view = renderHook(({ session }) => useInspectorState(session, false), { initialProps: { session: "a" } })
  act(() => view.result.current.toggleDesktop())
  act(() => view.result.current.toggleExpanded())
  expect(view.result.current.expanded).toBe(true)
  view.rerender({ session: "b" })
  expect(view.result.current.expanded).toBe(false)
  expect(view.result.current.overlay).toBe(false)
  expect(view.result.current.collapsed).toBe(true)
  view.rerender({ session: "a" })
  expect(view.result.current.expanded).toBe(true)
  act(() => view.result.current.close())
  expect(view.result.current.expanded).toBe(false)
})
it("dismisses quote overlays without discarding the desktop visibility choice", () => {
  const view = renderHook(() => useInspectorState("a", true))
  act(() => view.result.current.reveal())
  act(() => view.result.current.toggleExpanded())
  act(() => view.result.current.dismissOverlay())
  expect(view.result.current.expanded).toBe(false)
  expect(view.result.current.overlay).toBe(false)
  expect(view.result.current.collapsed).toBe(false)
})
