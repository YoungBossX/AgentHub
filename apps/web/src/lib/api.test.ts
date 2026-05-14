import { describe, expect, it, vi } from "vitest"

import {
  createWorkspaceSession,
  getBackendHealth,
  getDemoWorkspace,
  listWorkspaceSessions,
} from "./api"

describe("getBackendHealth", () => {
  it("fetches the backend health endpoint", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "agenthub-api",
          database: "ready",
        }),
        { status: 200 },
      )
    })

    const health = await getBackendHealth("http://127.0.0.1:8000", fetchMock)

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/health", {
      cache: "no-store",
    })
    expect(health).toEqual({
      status: "ok",
      service: "agenthub-api",
      database: "ready",
    })
  })
})

describe("workspace and session API", () => {
  it("fetches the demo workspace", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          id: "workspace-1",
          name: "AgentHub Demo",
          repoUrl: "local://apps/demo",
          rootPath: "apps/demo",
          defaultBranch: "main",
          createdAt: "2026-05-14T00:00:00Z",
        }),
        { status: 200 },
      )
    })

    const workspace = await getDemoWorkspace("http://127.0.0.1:8000", fetchMock)

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/workspaces/demo", {
      cache: "no-store",
    })
    expect(workspace?.rootPath).toBe("apps/demo")
  })

  it("lists and creates sessions for a workspace", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString()
      if (url.endsWith("/sessions") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "session-2",
            workspaceId: "workspace-1",
            title: "Second session",
            sessionType: "demo",
            boundBranch: "main",
            worktreePath: "/repo/.worktrees/workspace-1/session-2",
            status: "active",
            lastMessageAt: "2026-05-14T00:00:00Z",
            createdAt: "2026-05-14T00:00:00Z",
            updatedAt: "2026-05-14T00:00:00Z",
          }),
          { status: 201 },
        )
      }

      return new Response(
        JSON.stringify([
          {
            id: "session-1",
            workspaceId: "workspace-1",
            title: "First session",
            sessionType: "demo",
            boundBranch: "main",
            worktreePath: "/repo/.worktrees/workspace-1/session-1",
            status: "active",
            lastMessageAt: "2026-05-14T00:00:00Z",
            createdAt: "2026-05-14T00:00:00Z",
            updatedAt: "2026-05-14T00:00:00Z",
          },
        ]),
        { status: 200 },
      )
    })

    const sessions = await listWorkspaceSessions(
      "http://127.0.0.1:8000",
      "workspace-1",
      fetchMock,
    )
    const created = await createWorkspaceSession(
      "http://127.0.0.1:8000",
      "workspace-1",
      "Second session",
      fetchMock,
    )

    expect(sessions).toHaveLength(1)
    expect(created.worktreePath).toBe("/repo/.worktrees/workspace-1/session-2")
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/workspaces/workspace-1/sessions",
      {
        body: JSON.stringify({ title: "Second session" }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      },
    )
  })
})
