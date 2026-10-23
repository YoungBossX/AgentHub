import { act, cleanup, render, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import type { ChatMessage } from "@/lib/api"
import type { MessagePage } from "@/lib/message-history-api"
import { mergeHistoryRows, useMessageHistory } from "./use-message-history"
import { ChatThread } from "./chat-thread"

const api = vi.hoisted(() => ({ page: vi.fn() }))
vi.mock("@/lib/message-history-api", async original => ({ ...await original<typeof import("@/lib/message-history-api")>(), listMessagePage: api.page }))
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)
const row = (n: number, sessionId = "s"): ChatMessage => ({ id: `row-${String(n).padStart(4, "0")}`, sessionId, senderType: "user", senderId: null,
  contentMd: `历史消息 ${n}`, messageKind: "chat", parentMessageId: null, streamState: "complete", createdAt: "2026-10-15T00:00:00Z" })
const rows = (start: number, end: number, sid = "s") => Array.from({ length: end - start }, (_, index) => row(start + index, sid))
const page = (messages: ChatMessage[], hasOlder = true, hasNewer = false): MessagePage => ({ messages, pinnedMessages: [], pinnedTotal: 0, total: 5000,
  hasOlder, hasNewer, olderCursor: messages[0]?.id ?? null, newerCursor: messages.at(-1)?.id ?? null, latestMessageId: row(4999).id, previewCharacterLimit: 12000 })
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done }); return { promise, resolve } }

it("bounds rendering and retains stable ordering and identity through older/newer merges", () => {
  expect(mergeHistoryRows(rows(0, 150), rows(100, 300), "newer").map(r => r.id)).toEqual(rows(100, 300).map(r => r.id))
  expect(mergeHistoryRows(rows(100, 300), rows(0, 150), "older").map(r => r.id)).toEqual(rows(0, 200).map(r => r.id))
  const { container } = render(<ChatThread messages={rows(0, 1000)} selectedSession={null} taskCount={0} />)
  expect(container.querySelectorAll('[id^="message-row-"]')).toHaveLength(200)
})

it("merges an older page with a simultaneous SSE update, keeps the chosen history and offers newer navigation", async () => {
  const older = deferred<MessagePage>()
  api.page.mockResolvedValueOnce(page(rows(4920, 5000))).mockImplementationOnce(() => older.promise)
  const revision = { current: 0 }, error = vi.fn()
  const hook = renderHook(() => useMessageHistory("api", "s", revision, error, vi.fn()))
  await waitFor(() => expect(hook.result.current.messages).toHaveLength(80))
  let loading!: Promise<void>
  act(() => { loading = hook.result.current.older() })
  act(() => hook.result.current.setMessages([...rows(4921, 5000), row(5000)]))
  await act(async () => { older.resolve({ ...page(rows(4840, 4920), true, true), latestMessageId: row(5000).id }); await loading })
  expect(hook.result.current.messages).toHaveLength(160)
  expect(hook.result.current.messages[0].id).toBe(row(4840).id)
  expect(hook.result.current.messages.some(r => r.id === row(5000).id)).toBe(false)
  expect(hook.result.current.hasNewer).toBe(true)
  expect(hook.result.current.latestMessages.at(-1)?.id).toBe(row(5000).id)
  expect(error).not.toHaveBeenCalled()
})

it("never grows beyond 200, and keeps pin edits made during paging", async () => {
  api.page.mockResolvedValueOnce(page(rows(4920, 5000)))
    .mockResolvedValueOnce(page(rows(4840, 4920), true, true))
    .mockResolvedValueOnce(page(rows(4760, 4840), true, true))
  const revision = { current: 0 }
  const hook = renderHook(() => useMessageHistory("api", "s", revision, vi.fn(), vi.fn()))
  await waitFor(() => expect(hook.result.current.messages).toHaveLength(80))
  await act(async () => { await hook.result.current.older() })
  act(() => hook.result.current.setMessages(current => current.map(r => r.id === row(4850).id ? { ...r, pinnedAt: "2026-10-15T01:00:00Z" } : r)))
  await act(async () => { await hook.result.current.older() })
  expect(hook.result.current.messages).toHaveLength(200)
  expect(hook.result.current.messages.find(r => r.id === row(4850).id)?.pinnedAt).toBeTruthy()
  expect(hook.result.current.messages[0].id).toBe(row(4760).id)
  expect(hook.result.current.historical).toBe(true)
})

it("ignores an old Session page even after switching away and back", async () => {
  const old = deferred<MessagePage>()
  api.page.mockResolvedValueOnce(page(rows(4920, 5000))).mockImplementationOnce(() => old.promise)
    .mockResolvedValueOnce(page(rows(0, 2, "other"), false)).mockResolvedValueOnce(page(rows(4920, 5000)))
  const revision = { current: 0 }
  const hook = renderHook(({ sid }) => useMessageHistory("api", sid, revision, vi.fn(), vi.fn()), { initialProps: { sid: "s" } })
  await waitFor(() => expect(hook.result.current.messages).toHaveLength(80))
  let pending!: Promise<void>
  act(() => { pending = hook.result.current.older() })
  hook.rerender({ sid: "other" })
  await waitFor(() => expect(hook.result.current.messages[0]?.sessionId).toBe("other"))
  hook.rerender({ sid: "s" })
  await waitFor(() => expect(hook.result.current.messages).toHaveLength(80))
  await act(async () => { old.resolve(page(rows(0, 80))); await pending })
  expect(hook.result.current.messages[0].id).toBe(row(4920).id)
})

it("locates a pin outside the visible window without loading all history", async () => {
  api.page.mockResolvedValueOnce({ ...page(rows(4920, 5000)), pinnedMessages: [{ ...row(10), pinnedAt: "2026-10-15" }], pinnedTotal: 40 })
    .mockResolvedValueOnce(page(rows(0, 80), false, true))
  const revision = { current: 0 }, hook = renderHook(() => useMessageHistory("api", "s", revision, vi.fn(), vi.fn()))
  await waitFor(() => expect(hook.result.current.messages).toHaveLength(80))
  act(() => hook.result.current.openMessage(row(10).id))
  await waitFor(() => expect(hook.result.current.messages[0].id).toBe(row(0).id))
  expect(api.page).toHaveBeenLastCalledWith("api", "s", { around: row(10).id })
  expect(hook.result.current.historical).toBe(true)
})

it("refreshes visible historical metadata and the latest tail without moving the reading window", async () => {
  api.page.mockResolvedValueOnce(page(rows(4920, 5000))).mockResolvedValueOnce(page(rows(4840, 4920), true, true))
  const revision = { current: 0 }, hook = renderHook(() => useMessageHistory("api", "s", revision, vi.fn(), vi.fn()))
  await waitFor(() => expect(hook.result.current.messages).toHaveLength(80))
  await act(async () => { await hook.result.current.older() })
  api.page.mockResolvedValueOnce({ ...page(rows(4921, 5001)), latestMessageId: row(5000).id, pinnedMessages: [{ ...row(10), pinnedAt: "2026-10-15" }], pinnedTotal: 40 })
    .mockResolvedValueOnce(page(rows(4840, 5000).map(r => r.id === row(4850).id ? { ...r, contentMd: "更新后的历史消息" } : r), true, true))
  await act(async () => { await hook.result.current.refresh() })
  expect(hook.result.current.messages[0].id).toBe(row(4840).id)
  expect(hook.result.current.messages).toHaveLength(160)
  expect(hook.result.current.messages.find(r => r.id === row(4850).id)?.contentMd).toBe("更新后的历史消息")
  expect(hook.result.current.messages.some(r => r.id === row(5000).id)).toBe(false)
  expect(hook.result.current.latestMessages.at(-1)?.id).toBe(row(5000).id)
  expect(hook.result.current.pinnedTotal).toBe(40)
  expect(hook.result.current.hasNewer).toBe(true)
  expect(api.page).toHaveBeenLastCalledWith("api", "s", { around: row(4920).id, limit: 160 })
})

it("scrolls to a requested message only after its page has committed to the DOM", async () => {
  api.page.mockResolvedValueOnce(page(rows(4920, 5000))).mockResolvedValueOnce(page(rows(0, 80), false, true))
    .mockResolvedValueOnce(page(rows(4920, 5001)))
  const revision = { current: 0 }, scrolled: string[] = []
  function View() {
    const history = useMessageHistory("api", "s", revision, vi.fn(), vi.fn())
    return <><button onClick={() => history.openMessage(row(10).id)}>pin</button><button onClick={() => void history.latest()}>latest</button>
      {history.messages.map(message => <div key={message.id} id={`message-${message.id}`} ref={element => {
        if (element) element.scrollIntoView = () => { expect(element.isConnected).toBe(true); scrolled.push(message.id) }
      }} />)}</>
  }
  const view = render(<View />)
  await waitFor(() => expect(view.container.querySelector(`#message-${row(4999).id}`)).toBeTruthy())
  act(() => view.getByText("pin").click())
  await waitFor(() => expect(scrolled).toContain(row(10).id))
  act(() => view.getByText("latest").click())
  await waitFor(() => expect(view.container.querySelector(`#message-${row(5000).id}`)).toBeTruthy())
  // Latest is owned by ConversationScroll, including the progress/results footer.
  expect(scrolled).toEqual([row(10).id])
})

it("reports manual refresh errors, clears pending and preserves the visible window", async () => {
  const failure = new Error("读取暂时不可用"), error = vi.fn(), ready = vi.fn(), revision = { current: 0 }
  api.page.mockResolvedValueOnce(page(rows(4920, 5000))).mockRejectedValueOnce(failure).mockResolvedValueOnce(page(rows(4920, 5000)))
  const hook = renderHook(() => useMessageHistory("api", "s", revision, error, ready))
  await waitFor(() => expect(hook.result.current.messages).toHaveLength(80))
  await act(async () => { await hook.result.current.refreshManually() })
  expect(error).toHaveBeenCalledWith(failure)
  expect(hook.result.current.pending).toBe(false)
  expect(hook.result.current.messages[0].id).toBe(row(4920).id)
  ready.mockClear()
  await act(async () => { await hook.result.current.refreshManually() })
  expect(ready).toHaveBeenCalledOnce()
})

it("does not report a late manual refresh failure in another session", async () => {
  let reject!: (reason: Error) => void
  const pending = new Promise<MessagePage>((_, fail) => { reject = fail })
  const revision = { current: 0 }, error = vi.fn(), ready = vi.fn()
  api.page.mockResolvedValueOnce(page(rows(4920, 5000))).mockImplementationOnce(() => pending).mockResolvedValueOnce(page(rows(0, 2, "other"), false))
  const hook = renderHook(({ sid }) => useMessageHistory("api", sid, revision, error, ready), { initialProps: { sid: "s" } })
  await waitFor(() => expect(hook.result.current.messages).toHaveLength(80))
  let refresh!: Promise<void>
  act(() => { refresh = hook.result.current.refreshManually() })
  expect(hook.result.current.pending).toBe(true)
  hook.rerender({ sid: "other" })
  await waitFor(() => expect(hook.result.current.messages[0]?.sessionId).toBe("other"))
  ready.mockClear()
  await act(async () => { reject(new Error("旧会话读取失败")); await refresh })
  expect(error).not.toHaveBeenCalled()
  expect(ready).not.toHaveBeenCalled()
  expect(hook.result.current.pending).toBe(false)
})
