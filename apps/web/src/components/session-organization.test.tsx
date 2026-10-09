import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { ChatMessage, WorkspaceSession } from "@/lib/api"
import { SessionSidebar } from "./session-sidebar"
import { ChatThread } from "./chat-thread"
import { formatCompactDateTime } from "@/lib/date-format"

afterEach(cleanup)
const session = (id: string, overrides: Partial<WorkspaceSession> = {}): WorkspaceSession => ({ id, title: id, workspaceId: "ws", sessionType: "demo", status: "active", worktreePath: "/worktree/"+id, boundBranch: "main", lastMessageAt: "2026-10-08T00:00:00", createdAt: "2026-10-08T00:00:00", updatedAt: "2026-10-08T00:00:00", ...overrides })
const sidebarProps = { agents: [], isPending: false, onCreateSession: vi.fn(), onSelectSession: vi.fn(), selectedSessionId: "recent", taskCount: 0, workspace: { id: "ws", name: "Workspace", repoUrl: "local", rootPath: "demo", defaultBranch: "main", createdAt: "2026-10-08" } }

describe("session organization", () => {
  it("orders pins before recents, separates archives, searches within the view and restores", () => {
    const organize = vi.fn()
    const sessions = [session("recent", { lastMessageAt: "2026-10-08T10:00:00" }), session("pinned", { pinnedAt: "2026-10-08T01:00:00" }), session("archive", { archivedAt: "2026-10-08T01:00:00" })]
    const { container } = render(<SessionSidebar {...sidebarProps} sessions={sessions} onOrganizeSession={organize} />)
    expect([...container.querySelectorAll("[data-session-id]")].map(el => el.getAttribute("data-session-id"))).toEqual(["pinned", "recent"])
    expect(screen.queryByRole("button", { name: "恢复会话：archive" })).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "取消置顶会话：pinned" }))
    expect(organize).toHaveBeenCalledWith("pinned", { pinned: false })
    fireEvent.click(screen.getByRole("button", { name: "归档会话：recent" }))
    expect(organize).toHaveBeenCalledWith("recent", { archived: true })
    fireEvent.click(screen.getByRole("button", { name: "已归档" }))
    expect([...container.querySelectorAll("[data-session-id]")].map(el => el.getAttribute("data-session-id"))).toEqual(["archive"])
    fireEvent.click(screen.getByRole("button", { name: "恢复会话：archive" }))
    expect(organize).toHaveBeenCalledWith("archive", { archived: false })
    fireEvent.change(screen.getByRole("searchbox", { name: "搜索会话" }), { target: { value: "recent" } })
    expect(container.querySelector("[data-session-id]")).toBeNull()
  })
  it("direct archived selection opens the archive view and action buttons do not select rows", () => {
    const select = vi.fn(), organize = vi.fn()
    const { container } = render(<SessionSidebar {...sidebarProps} selectedSessionId="archive" onSelectSession={select} sessions={[session("archive", { archivedAt: "date" })]} onOrganizeSession={organize} />)
    expect(screen.getByRole("button", { name: "已归档" }).getAttribute("aria-pressed")).toBe("true")
    fireEvent.click(screen.getByRole("button", { name: "置顶会话：archive" }))
    expect(select).not.toHaveBeenCalled()
    expect(container.querySelector("button button")).toBeNull()
  })
  it("orders session recency by instants rather than offset strings and searches displayed local time", () => {
    const earlier = session("offset", { lastMessageAt: "2026-10-08T13:00:00+08:00" })
    const later = session("utc", { lastMessageAt: "2026-10-08T06:00:00" })
    const { container } = render(<SessionSidebar {...sidebarProps} sessions={[earlier, later]} />)
    expect([...container.querySelectorAll("[data-session-id]")].map(el => el.getAttribute("data-session-id"))).toEqual(["utc", "offset"])
    const displayed = formatCompactDateTime(later.lastMessageAt!, Intl.DateTimeFormat().resolvedOptions().timeZone)
    fireEvent.change(screen.getByRole("searchbox", { name: "搜索会话" }), { target: { value: displayed } })
    expect([...container.querySelectorAll("[data-session-id]")].map(el => el.getAttribute("data-session-id"))).toEqual(["utc"])
  })

  it("disables organization actions while pending", () => {
    render(<SessionSidebar {...sidebarProps} isPending sessions={[session("recent")]} onOrganizeSession={vi.fn()} />)
    expect((screen.getByRole("button", { name: "置顶会话：recent" }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe("key message pins", () => {
  const message: ChatMessage = { id: "message-one", sessionId: "recent", senderType: "user", senderId: null, contentMd: "Original key message", messageKind: "chat", parentMessageId: null, streamState: "complete", createdAt: "2026-10-08" }
  it("pins/unpins and jumps to the original bubble without changing conversation order", () => {
    const pin = vi.fn(); const scroll = vi.fn()
    const { container, rerender } = render(<ChatThread messages={[message]} selectedSession={session("recent")} taskCount={0} onPinMessage={pin} />)
    fireEvent.click(screen.getByRole("button", { name: "置顶消息" }))
    expect(pin).toHaveBeenCalledWith(message, true)
    const pinned = { ...message, pinnedAt: "2026-10-08" }
    rerender(<ChatThread messages={[pinned]} selectedSession={session("recent")} taskCount={0} onPinMessage={pin} />)
    const bubble = container.querySelector("article")! as HTMLElement
    bubble.scrollIntoView = scroll
    fireEvent.click(within(screen.getByLabelText("关键消息")).getByRole("button", { name: message.contentMd }))
    expect(scroll).toHaveBeenCalledWith({ behavior: "smooth", block: "center" })
    fireEvent.click(screen.getByRole("button", { name: "取消置顶消息" }))
    expect(pin).toHaveBeenLastCalledWith(pinned, false)
    expect(bubble.id).toBe("message-message-one")
  })
  it("hides the empty key list and disables pin buttons while pending", () => {
    render(<ChatThread messages={[message]} selectedSession={session("recent")} taskCount={0} onPinMessage={vi.fn()} actionsPending />)
    expect(screen.queryByLabelText("关键消息")).toBeNull()
    expect((screen.getByRole("button", { name: "置顶消息" }) as HTMLButtonElement).disabled).toBe(true)
  })
})
