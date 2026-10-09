import { describe, expect, it, vi } from "vitest"
import { organizeSession, pinSessionMessage, listWorkspaceSessions, ApiRequestError } from "./api"

describe("organization transport", () => {
  it("updates only requested session metadata", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "s", pinnedAt: "date" }), { status: 200 }))
    await organizeSession("http://api/", "s", { pinned: true }, fetcher)
    expect(fetcher).toHaveBeenCalledWith("http://api/sessions/s/organization", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: '{"pinned":true}' })
  })
  it("pins within the supplied session and preserves backend errors", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Message not found in this Session" }), { status: 404 }))
    await expect(pinSessionMessage("http://api", "s", "m", true, fetcher)).rejects.toThrow(ApiRequestError)
    expect(fetcher.mock.calls[0][0]).toBe("http://api/sessions/s/messages/m/pin")
  })
  it("uses an explicit archive/all view while keeping the default active URL", async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(new Response("[]")))
    await listWorkspaceSessions("http://api", "ws", fetcher)
    await listWorkspaceSessions("http://api", "ws", fetcher, "all")
    await listWorkspaceSessions("http://api", "ws", fetcher, "archived")
    expect(fetcher.mock.calls.map(call => call[0])).toEqual(["http://api/workspaces/ws/sessions", "http://api/workspaces/ws/sessions?view=all", "http://api/workspaces/ws/sessions?view=archived"])
  })
})
