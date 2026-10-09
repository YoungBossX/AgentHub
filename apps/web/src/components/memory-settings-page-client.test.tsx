import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MemorySettingsPageClient } from "./memory-settings-page-client"
import type { MemoryItem, Workspace, WorkspaceSession } from "@/lib/api"

const apiMocks = vi.hoisted(() => ({
  getDemoWorkspace: vi.fn(),
  listWorkspaceMemory: vi.fn(),
  listWorkspaceSessions: vi.fn(),
  refreshSessionMemorySnapshot: vi.fn(),
  updateMemoryItemStatus: vi.fn(),
}))

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getDemoWorkspace: apiMocks.getDemoWorkspace,
  listWorkspaceMemory: apiMocks.listWorkspaceMemory,
  listWorkspaceSessions: apiMocks.listWorkspaceSessions,
  refreshSessionMemorySnapshot: apiMocks.refreshSessionMemorySnapshot,
  updateMemoryItemStatus: apiMocks.updateMemoryItemStatus,
}))

const workspace: Workspace = {
  createdAt: "2026-05-16T00:00:00Z",
  defaultBranch: "main",
  id: "workspace-1",
  name: "AgentHub Demo",
  repoUrl: "local://apps/demo",
  rootPath: "apps/demo",
}

const sessions: WorkspaceSession[] = [
  {
    activeBackendTargetId: "demo-backend",
    activeFrontendTargetId: "demo-frontend",
    boundBranch: "main",
    createdAt: "2026-05-16T00:00:00Z",
    id: "session-1",
    lastMessageAt: "2026-05-16T00:00:00Z",
    memorySnapshotId: "snapshot-1",
    sessionType: "demo",
    status: "active",
    title: "Memory session",
    updatedAt: "2026-05-16T00:00:00Z",
    workspaceId: "workspace-1",
    worktreePath: "/repo/.worktrees/session-1",
  },
]

const memoryItem: MemoryItem = {
  agentRoles: ["frontend"],
  compiledToAgentsMd: true,
  compiledToClaudeMd: true,
  contentHash: "hash",
  contentMd: "用户写中文时优先中文回复。",
  createdAt: "2026-05-16T00:00:00Z",
  id: "memory-1",
  importance: 80,
  lastUsedAt: null,
  memoryType: "user_preference",
  scope: "user",
  source: "user_explicit",
  status: "active",
  supersededBy: null,
  targetIds: ["demo-frontend"],
  title: "Chinese preference",
  trustLevel: "user_confirmed",
  updatedAt: "2026-05-16T00:00:00Z",
  version: 1,
  workspaceId: "workspace-1",
}

describe("MemorySettingsPageClient", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    apiMocks.getDemoWorkspace.mockResolvedValue(workspace)
    apiMocks.listWorkspaceSessions.mockResolvedValue(sessions)
    apiMocks.listWorkspaceMemory.mockResolvedValue([memoryItem])
    apiMocks.refreshSessionMemorySnapshot.mockResolvedValue({
      ...sessions[0],
      memorySnapshotId: "snapshot-new",
    })
    apiMocks.updateMemoryItemStatus.mockResolvedValue({
      ...memoryItem,
      compiledToAgentsMd: false,
      compiledToClaudeMd: false,
      status: "archived",
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("renders memory items with snapshot and outlet metadata", async () => {
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-1" />)

    expect(await screen.findByText("Chinese preference")).toBeTruthy()
    expect(screen.getByText(/snapshot-1/)).toBeTruthy()
    expect(screen.getAllByText("已编译").length).toBeGreaterThan(0)
    expect(apiMocks.listWorkspaceMemory).toHaveBeenCalledWith(
      "http://127.0.0.1:8000",
      "workspace-1",
      "active",
    )
  })

  it("archives memory from the active filter", async () => {
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-1" />)

    await screen.findByText("Chinese preference")
    fireEvent.click(screen.getByLabelText("归档"))

    await waitFor(() => {
      expect(apiMocks.updateMemoryItemStatus).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "memory-1",
        "archived",
      )
    })
    await waitFor(() => {
      expect(screen.queryByText("Chinese preference")).toBeNull()
    })
    expect(screen.getByText(/已更新：已归档/)).toBeTruthy()
    expect(screen.getByText(/snapshot-1/)).toBeTruthy()
    expect(apiMocks.refreshSessionMemorySnapshot).not.toHaveBeenCalled()
  })

  it("refreshes the selected session rather than the first snapshot", async () => {
    const second = { ...sessions[0], id: "session-2", title: "Second session", memorySnapshotId: "snapshot-2" }
    apiMocks.listWorkspaceSessions.mockResolvedValue([...sessions, second])
    apiMocks.refreshSessionMemorySnapshot.mockResolvedValue({ ...second, memorySnapshotId: "snapshot-new" })
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-2" />)

    await screen.findByText(/snapshot-2/)
    expect(screen.queryByText(/snapshot-1/)).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "刷新会话快照" }))
    await screen.findByText(/snapshot-new/)
    expect(apiMocks.refreshSessionMemorySnapshot).toHaveBeenCalledExactlyOnceWith("http://127.0.0.1:8000", "session-2")
    expect(screen.getByRole("link", { name: "返回聊天" }).getAttribute("href")).toBe("/?session=session-2")
    expect(screen.getByRole("status").textContent).toContain("会话快照已刷新")
  })

  it.each([undefined, "missing-session"])("requires explicit selection when initial session is %s", async (initialSessionId) => {
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId={initialSessionId} />)
    await screen.findByText("Chinese preference")
    const button = screen.getByRole("button", { name: "刷新会话快照" }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(screen.queryByText(/snapshot-1/)).toBeNull()
    fireEvent.change(screen.getByRole("combobox", { name: "会话" }), { target: { value: "session-1" } })
    expect(screen.getByText(/snapshot-1/)).toBeTruthy()
    expect(button.disabled).toBe(false)
    expect(apiMocks.refreshSessionMemorySnapshot).not.toHaveBeenCalled()
  })

  it("reloads the memory list without refreshing a snapshot", async () => {
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-1" />)
    await screen.findByText("Chinese preference")
    apiMocks.listWorkspaceMemory.mockResolvedValue([{ ...memoryItem, title: "Updated list" }])
    fireEvent.click(screen.getByRole("button", { name: "重新加载列表" }))
    await screen.findByText("Updated list")
    expect(apiMocks.refreshSessionMemorySnapshot).not.toHaveBeenCalled()
    expect(screen.getByText(/snapshot-1/)).toBeTruthy()
  })

  it("blocks duplicate refresh and conflicting controls while pending", async () => {
    let resolve!: (session: WorkspaceSession) => void
    apiMocks.refreshSessionMemorySnapshot.mockImplementation(() => new Promise<WorkspaceSession>((done) => { resolve = done }))
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-1" />)
    await screen.findByText("Chinese preference")
    fireEvent.click(screen.getByRole("button", { name: "刷新会话快照" }))
    const button = screen.getByRole("button", { name: "刷新中…" }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect((screen.getByRole("combobox") as HTMLSelectElement).disabled).toBe(true)
    expect((screen.getByLabelText("归档") as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole("button", { name: "待确认" }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(button)
    expect(apiMocks.refreshSessionMemorySnapshot).toHaveBeenCalledTimes(1)
    await act(async () => { resolve({ ...sessions[0], memorySnapshotId: "snapshot-new" }) })
    await screen.findByText(/snapshot-new/)
    expect((screen.getByRole("button", { name: "刷新会话快照" }) as HTMLButtonElement).disabled).toBe(false)
  })

  it("keeps the old binding on conflict and permits retry", async () => {
    apiMocks.refreshSessionMemorySnapshot.mockRejectedValueOnce(new Error("任务执行中，请等待结束后重试"))
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-1" />)
    await screen.findByText("Chinese preference")
    fireEvent.click(screen.getByRole("button", { name: "刷新会话快照" }))
    expect((await screen.findByRole("status")).textContent).toContain("等待结束后重试")
    expect(screen.getByText(/snapshot-1/)).toBeTruthy()
    expect(screen.queryByText(/会话快照已刷新/)).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "刷新会话快照" }))
    await screen.findByText(/snapshot-new/)
  })

  it.each([
    { id: "other" },
    { workspaceId: "foreign" },
    { memorySnapshotId: null },
  ])("rejects a response with mismatched identity or missing binding: %j", async (override) => {
    apiMocks.refreshSessionMemorySnapshot.mockResolvedValue({ ...sessions[0], memorySnapshotId: "foreign-snapshot", ...override })
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-1" />)
    await screen.findByText("Chinese preference")
    fireEvent.click(screen.getByRole("button", { name: "刷新会话快照" }))
    await screen.findByRole("status")
    expect(screen.getByText(/snapshot-1/)).toBeTruthy()
    expect(screen.queryByText(/foreign-snapshot/)).toBeNull()
    expect(screen.queryByText(/会话快照已刷新/)).toBeNull()
  })

  it("excludes sessions belonging to another workspace", async () => {
    apiMocks.listWorkspaceSessions.mockResolvedValue([{ ...sessions[0], workspaceId: "foreign" }])
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-1" />)
    await screen.findByText("Chinese preference")
    expect(screen.queryByRole("option", { name: "Memory session" })).toBeNull()
    expect((screen.getByRole("button", { name: "刷新会话快照" }) as HTMLButtonElement).disabled).toBe(true)
    expect(apiMocks.refreshSessionMemorySnapshot).not.toHaveBeenCalled()
  })

  it("allows explicit refresh for a session without a bound snapshot", async () => {
    apiMocks.listWorkspaceSessions.mockResolvedValue([{ ...sessions[0], memorySnapshotId: null }])
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-1" />)
    await screen.findByText("尚未绑定记忆快照")
    fireEvent.click(screen.getByRole("button", { name: "刷新会话快照" }))
    await screen.findByText(/snapshot-new/)
  })

  it("ignores a refresh response after switching the backend", async () => {
    let resolve!: (session: WorkspaceSession) => void
    apiMocks.refreshSessionMemorySnapshot.mockImplementation(() => new Promise<WorkspaceSession>((done) => { resolve = done }))
    const view = render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" initialSessionId="session-1" />)
    await screen.findByText("Chinese preference")
    fireEvent.click(screen.getByRole("button", { name: "刷新会话快照" }))
    apiMocks.listWorkspaceSessions.mockResolvedValue([{ ...sessions[0], memorySnapshotId: "snapshot-other-backend" }])
    view.rerender(<MemorySettingsPageClient backendUrl="http://127.0.0.1:9000" initialSessionId="session-1" />)
    await screen.findByText(/snapshot-other-backend/)
    await act(async () => { resolve({ ...sessions[0], memorySnapshotId: "stale-snapshot" }) })
    expect(screen.queryByText(/stale-snapshot/)).toBeNull()
    expect(screen.queryByText(/会话快照已刷新/)).toBeNull()
    expect(screen.getByText(/snapshot-other-backend/)).toBeTruthy()
  })
})
