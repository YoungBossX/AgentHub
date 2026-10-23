import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { Disclosure } from "./disclosure"

afterEach(cleanup)
it("keeps collapsed children inert and connects the keyboard-operable trigger", () => {
  render(<Disclosure summary="执行依据"><button>查看 Diff</button></Disclosure>)
  const trigger = screen.getByRole("button", { name: "执行依据" })
  const panel = document.getElementById(trigger.getAttribute("aria-controls")!)!
  expect(trigger.getAttribute("aria-expanded")).toBe("false")
  expect(panel.hasAttribute("inert")).toBe(true)
  fireEvent.click(trigger)
  expect(trigger.getAttribute("aria-expanded")).toBe("true")
  expect(panel.hasAttribute("inert")).toBe(false)
  expect(screen.getByRole("button", { name: "查看 Diff" })).toBeTruthy()
  fireEvent.click(trigger)
  expect(panel.hasAttribute("inert")).toBe(true)
})
it("supports initially open evidence and notifies only on a user toggle", () => {
  const onOpenChange = vi.fn()
  render(<Disclosure defaultOpen summary="历史" onOpenChange={onOpenChange}>证据</Disclosure>)
  expect(onOpenChange).not.toHaveBeenCalled()
  const trigger = screen.getByRole("button", { name: "历史" })
  expect(trigger.getAttribute("aria-expanded")).toBe("true")
  fireEvent.click(trigger)
  expect(onOpenChange).toHaveBeenCalledWith(false)
})
