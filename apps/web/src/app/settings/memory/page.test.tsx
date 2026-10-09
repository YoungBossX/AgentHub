import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import MemorySettingsPage from "./page"

vi.mock("@/components/memory-settings-page-client", () => ({
  MemorySettingsPageClient: ({ initialSessionId }: { initialSessionId: string | null }) => (
    <div data-testid="selected-session">{initialSessionId ?? "unselected"}</div>
  ),
}))

afterEach(cleanup)

describe("memory settings navigation", () => {
  it.each([
    [{ session: "session-2" }, "session-2"],
    [{}, "unselected"],
    [{ session: ["session-1", "session-2"] }, "unselected"],
  ])("passes a single unambiguous query selection to the client", async (params, expected) => {
    render(await MemorySettingsPage({ searchParams: Promise.resolve(params) }))
    expect(screen.getByTestId("selected-session").textContent).toBe(expected)
  })
})
