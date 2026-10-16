import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import type { ChatMessage } from "@/lib/api"
import { LongMessageContent } from "./long-message-content"

const api = vi.hoisted(() => ({ read: vi.fn() }))
vi.mock("@/lib/message-history-api", () => ({ getMessageContent: api.read }))
afterEach(() => { cleanup(); vi.clearAllMocks() })
it("reads explicit bounded Unicode segments without combining a full body", async () => {
  api.read.mockResolvedValueOnce({ messageId: "m", text: "中文😀", offset: 0, totalCharacters: 6, nextOffset: 3, previousOffset: null })
    .mockResolvedValueOnce({ messageId: "m", text: "下一段", offset: 3, totalCharacters: 6, nextOffset: null, previousOffset: 0 })
  const { container } = render(<LongMessageContent backendUrl="api" message={{ id: "m", sessionId: "s", contentTruncated: true } as ChatMessage} />)
  expect(api.read).not.toHaveBeenCalled()
  const details = container.querySelector("details")!; details.open = true; fireEvent(details, new Event("toggle"))
  expect(await screen.findByText("中文😀")).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "下一段" }))
  await waitFor(() => expect(api.read).toHaveBeenLastCalledWith("api", "s", "m", 3))
  expect(await screen.findByText("下一段", { selector: "pre" })).toBeTruthy()
  expect(screen.queryByText("中文😀", { selector: "pre" })).toBeNull()
})
