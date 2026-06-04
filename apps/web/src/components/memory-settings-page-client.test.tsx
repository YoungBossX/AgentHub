import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MemorySettingsPageClient } from "./memory-settings-page-client"
import type { MemoryItem, Workspace, WorkspaceSession } from "@/lib/api"

const apiMocks = vi.hoisted(() => ({
  getDemoWorkspace: vi.fn(),
  listWorkspaceMemory: vi.fn(),
  listWorkspaceSessions: vi.fn(),
  updateMemoryItemStatus: vi.fn(),
}))

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getDemoWorkspace: apiMocks.getDemoWorkspace,
  listWorkspaceMemory: apiMocks.listWorkspaceMemory,
  listWorkspaceSessions: apiMocks.listWorkspaceSessions,
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
    apiMocks.getDemoWorkspace.mockResolvedValue(workspace)
    apiMocks.listWorkspaceSessions.mockResolvedValue(sessions)
    apiMocks.listWorkspaceMemory.mockResolvedValue([memoryItem])
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
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" />)

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
    render(<MemorySettingsPageClient backendUrl="http://127.0.0.1:8000" />)

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
    expect(screen.getByText("已更新：已归档")).toBeTruthy()
  })
})
