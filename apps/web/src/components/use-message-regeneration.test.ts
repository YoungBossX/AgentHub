import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { useMessageRegeneration } from "./use-message-regeneration"
import type { ChatMessage } from "@/lib/api"

const api = vi.hoisted(() => ({ regenerate: vi.fn(), messages: vi.fn(), tasks: vi.fn(), locate: vi.fn() }))
vi.mock("@/lib/message-history-api", async original => ({ ...await original<typeof import("@/lib/message-history-api")>(), getHistoryMessage: api.locate,
  listMessagePage: async () => ({ messages: await api.messages(), pinnedMessages: [], pinnedTotal: 0, total: 0, hasOlder: false, hasNewer: false, latestMessageId: null }),
}))
vi.mock("@/lib/api", async (original) => ({ ...await original<typeof import("@/lib/api")>(), regenerateSessionMessage: api.regenerate, listSessionMessages: api.messages, listSessionTasks: api.tasks }))
const message = { id: "reply", sessionId: "a" } as ChatMessage
const created = { id: "operation", sessionId: "a", regeneration: { sourceMessageId: "reply", state: "submitted" } } as ChatMessage
beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); api.tasks.mockResolvedValue([]); api.messages.mockResolvedValue([created]); api.locate.mockRejectedValue(new Error("not found")) })
afterEach(cleanup)

it("resolves the exact operation outside the bounded latest page", async () => {
  api.regenerate.mockImplementation(async (_url, _session, _message, id) => {
    api.locate.mockResolvedValue({ ...created, id })
    throw new Error("lost response")
  })
  api.messages.mockResolvedValue([])
  const apply = vi.fn(), hook = renderHook(() => useMessageRegeneration("", "a", apply))
  await act(async () => { await hook.result.current.run(message) })
  expect(api.locate).toHaveBeenCalledWith("", "a", api.regenerate.mock.calls[0][3])
  expect(api.regenerate).toHaveBeenCalledTimes(1)
  expect(apply).toHaveBeenCalledWith("a", [], [], expect.objectContaining({ regeneration: created.regeneration }), expect.objectContaining({ messages: [] }))
})

it("retains operation identity across network uncertainty, rerender and remount", async () => {
  api.regenerate.mockRejectedValue(new Error("network")); api.messages.mockResolvedValue([])
  const first = renderHook(() => useMessageRegeneration("", "a", vi.fn()))
  await act(async () => { await expect(first.result.current.run(message)).rejects.toThrow("同一次操作") })
  const id = api.regenerate.mock.calls[0][3]
  first.unmount()
  const apply = vi.fn(); const second = renderHook(() => useMessageRegeneration("", "a", apply))
  api.regenerate.mockResolvedValue(created); api.messages.mockResolvedValue([created])
  await act(async () => { await second.result.current.run(message) })
  expect(api.regenerate.mock.calls[1][3]).toBe(id)
  expect(apply).toHaveBeenCalledWith("a", [created], [], created, expect.objectContaining({ messages: [created] }))
  expect(sessionStorage.length).toBe(0)
})

it("resolves a lost successful response from history instead of making another generation", async () => {
  api.regenerate.mockImplementation(async (_url, _session, _message, id) => {
    api.messages.mockResolvedValue([{ ...created, id }]); throw new Error("response lost")
  })
  const apply = vi.fn(); const hook = renderHook(() => useMessageRegeneration("", "a", apply))
  await act(async () => { await hook.result.current.run(message) })
  expect(api.regenerate).toHaveBeenCalledTimes(1)
  expect(apply).toHaveBeenCalledTimes(1)
})

it("keeps the source Session when switching and ignores duplicate in-flight clicks", async () => {
  let resolve!: (value: ChatMessage) => void
  api.regenerate.mockImplementation(() => new Promise<ChatMessage>((done) => { resolve = done }))
  const apply = vi.fn(); const hook = renderHook(({ session }) => useMessageRegeneration("", session, apply), { initialProps: { session: "a" } })
  let pending!: Promise<void>
  act(() => { pending = hook.result.current.run(message) })
  await act(async () => { await hook.result.current.run(message) })
  expect(api.regenerate).toHaveBeenCalledTimes(1)
  hook.rerender({ session: "b" })
  expect(hook.result.current.pending).toBe(false)
  await act(async () => { resolve(created); await pending })
  expect(apply.mock.calls[0][0]).toBe("a")
})
