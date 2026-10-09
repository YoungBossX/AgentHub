import { act, cleanup, render } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useSessionEventRefresh } from "./use-session-event-refresh"

const mocks = vi.hoisted(() => ({ tasks: vi.fn(), messages: vi.fn() }))
vi.mock("@/lib/api", async (original) => ({ ...await original<typeof import("@/lib/api")>(), listSessionTasks: mocks.tasks, listSessionMessages: mocks.messages }))
const setMessages = vi.fn(), setTasks = vi.fn(), reportSyncError = vi.fn(), setArtifactRefreshVersion = vi.fn(), setSyncError = vi.fn()
class Source { close = vi.fn() }
function Harness({ sessionId, pending, revision }: { sessionId: string; pending: boolean; revision?: { current: number } }) {
  useSessionEventRefresh({ backendUrl: "http://local", selectedSessionId: sessionId, summaryPending: pending, messageRevisionRef: revision, setMessages, setTasks, reportSyncError, setArtifactRefreshVersion, setSyncError })
  return null
}
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.clearAllMocks() })
describe("pending group summary recovery", () => {
  it("rejects an older refresh after a pin mutation and requests fresh messages", async () => {
    vi.useFakeTimers(); vi.stubGlobal("EventSource", Source)
    const revision = { current: 0 }
    let resolve!: (value: []) => void
    const fresh = [{ id: "fresh", pinnedAt: "persisted" }]
    mocks.tasks.mockResolvedValue([])
    mocks.messages.mockImplementationOnce(() => new Promise((done) => { resolve = done })).mockResolvedValue(fresh)
    render(<Harness sessionId="one" pending revision={revision} />)
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    revision.current += 1
    await act(async () => { resolve([]); await vi.advanceTimersByTimeAsync(0) })
    expect(setMessages).toHaveBeenCalledTimes(1)
    expect(setMessages).toHaveBeenCalledWith(fresh)
    expect(mocks.messages).toHaveBeenCalledTimes(2)
  })
  it("polls only while pending without recreating SSE and stops on cleanup", async () => {
    vi.useFakeTimers(); const source = vi.fn(function () { return new Source() }); vi.stubGlobal("EventSource", source)
    mocks.tasks.mockResolvedValue([]); mocks.messages.mockResolvedValue([])
    const { rerender, unmount } = render(<Harness sessionId="one" pending={false} />)
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(mocks.tasks).not.toHaveBeenCalled()
    rerender(<Harness sessionId="one" pending />)
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(mocks.tasks).toHaveBeenCalledWith("http://local", "one")
    expect(mocks.messages).toHaveBeenCalledWith("http://local", "one")
    expect(source).toHaveBeenCalledTimes(1)
    rerender(<Harness sessionId="one" pending={false} />)
    await act(async () => { await vi.advanceTimersByTimeAsync(4000) })
    expect(mocks.tasks).toHaveBeenCalledTimes(1)
    unmount(); await act(async () => { await vi.advanceTimersByTimeAsync(4000) })
    expect(mocks.tasks).toHaveBeenCalledTimes(1)
  })
  it("ignores the old session response after switching", async () => {
    vi.useFakeTimers(); vi.stubGlobal("EventSource", Source)
    let resolve!: (value: []) => void
    mocks.tasks.mockImplementationOnce(() => new Promise((done) => { resolve = done })).mockResolvedValue([])
    mocks.messages.mockResolvedValue([])
    const { rerender } = render(<Harness sessionId="one" pending />)
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    rerender(<Harness sessionId="two" pending={false} />)
    await act(async () => { resolve([]); await Promise.resolve() })
    expect(setTasks).not.toHaveBeenCalled()
    expect(setMessages).not.toHaveBeenCalled()
  })
})
