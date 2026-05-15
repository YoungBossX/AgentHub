import { describe, expect, it, vi } from "vitest"

import {
  createSessionMessage,
  createTaskRun,
  createWorkspaceSession,
  getBackendHealth,
  getDemoWorkspace,
  interruptTaskRun,
  listTaskRunDiffs,
  listSessionMessages,
  listSessionTasks,
  listWorkspaceSessions,
  retryTaskRun,
  retryTaskRunWithFallback,
  sessionEventsUrl,
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

describe("message and event API", () => {
  it("lists and creates messages for a selected session", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString()
      if (url.endsWith("/messages") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "message-2",
            sessionId: "session-1",
            senderType: "user",
            senderId: null,
            contentMd: "@orchestrator build a login page",
            messageKind: "chat",
            parentMessageId: null,
            streamState: "complete",
            createdAt: "2026-05-14T00:00:00Z",
          }),
          { status: 201 },
        )
      }

      return new Response(
        JSON.stringify([
          {
            id: "message-1",
            sessionId: "session-1",
            senderType: "system",
            senderId: null,
            contentMd: "Session ready",
            messageKind: "chat",
            parentMessageId: null,
            streamState: "complete",
            createdAt: "2026-05-14T00:00:00Z",
          },
        ]),
        { status: 200 },
      )
    })

    const messages = await listSessionMessages(
      "http://127.0.0.1:8000",
      "session-1",
      fetchMock,
    )
    const created = await createSessionMessage(
      "http://127.0.0.1:8000",
      "session-1",
      "@orchestrator build a login page",
      fetchMock,
    )

    expect(messages[0].contentMd).toBe("Session ready")
    expect(created.senderType).toBe("user")
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/sessions/session-1/messages",
      {
        body: JSON.stringify({
          contentMd: "@orchestrator build a login page",
          senderType: "user",
        }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      },
    )
  })

  it("builds an SSE subscription URL for a selected session", () => {
    expect(sessionEventsUrl("http://127.0.0.1:8000", "session-1", 4)).toBe(
      "http://127.0.0.1:8000/sessions/session-1/events?after=4&stream=true",
    )
  })
})

describe("task API", () => {
  it("lists visible task cards for a selected session", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify([
          {
            id: "task-1",
            sessionId: "session-1",
            createdByMessageId: "message-1",
            title: "Build the Vite React login page",
            intentType: "frontend_change",
            status: "pending",
            priority: 1,
            planJson: { target: "login_page" },
            dependsOnTaskIds: ["task-0"],
            assignedAgentId: "agent-frontend",
            assignedAgentRole: "frontend",
            taskRuns: [
              {
                id: "run-1",
                taskId: "task-1",
                sessionId: "session-1",
                agentId: "agent-frontend",
                adapterType: "codex",
                adapterRunId: null,
                state: "failed",
                startedAt: null,
                endedAt: "2026-05-14T00:00:01Z",
                worktreePath: "/repo/.worktrees/session-1",
                baseRef: null,
                headRef: null,
                errorCode: "CODEX_USAGE_LIMIT",
                errorMessage: "Usage limit reached.",
                metricsJson: { adapterType: "codex" },
                createdAt: "2026-05-14T00:00:00Z",
                updatedAt: "2026-05-14T00:00:01Z",
              },
            ],
            createdAt: "2026-05-14T00:00:00Z",
            updatedAt: "2026-05-14T00:00:00Z",
          },
        ]),
        { status: 200 },
      )
    })

    const tasks = await listSessionTasks(
      "http://127.0.0.1:8000",
      "session-1",
      fetchMock,
    )

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/sessions/session-1/tasks",
      {
        cache: "no-store",
      },
    )
    expect(tasks[0].assignedAgentRole).toBe("frontend")
    expect(tasks[0].dependsOnTaskIds).toEqual(["task-0"])
    expect(tasks[0].taskRuns[0].adapterType).toBe("codex")
  })

  it("creates, interrupts, retries, and falls back task runs", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      const payload = {
        id: "run-2",
        taskId: "task-1",
        sessionId: "session-1",
        agentId: "agent-frontend",
        adapterType: url.endsWith("retry-with-fallback") ? "scripted_mock" : "codex",
        adapterRunId: null,
        state: "queued",
        startedAt: null,
        endedAt: null,
        worktreePath: "/repo/.worktrees/session-1",
        baseRef: null,
        headRef: null,
        errorCode: null,
        errorMessage: null,
        metricsJson: {},
        createdAt: "2026-05-14T00:00:00Z",
        updatedAt: "2026-05-14T00:00:00Z",
      }
      return new Response(JSON.stringify(payload), { status: 201 })
    })

    await createTaskRun("http://127.0.0.1:8000", "task-1", fetchMock)
    await interruptTaskRun("http://127.0.0.1:8000", "run-1", fetchMock)
    await retryTaskRun("http://127.0.0.1:8000", "run-1", fetchMock)
    const fallback = await retryTaskRunWithFallback(
      "http://127.0.0.1:8000",
      "run-1",
      fetchMock,
    )

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/tasks/task-1/runs",
      { method: "POST" },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/task-runs/run-1/interrupt",
      { method: "POST" },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/task-runs/run-1/retry",
      { method: "POST" },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/task-runs/run-1/retry-with-fallback",
      { method: "POST" },
    )
    expect(fallback.adapterType).toBe("scripted_mock")
  })

  it("lists diff artifacts for a task run", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify([
          {
            id: "diff-1",
            artifactId: "artifact-1",
            taskRunId: "run-1",
            artifactType: "diff",
            title: "Git diff",
            status: "ready",
            baseRef: "abc123",
            headRef: "def456+worktree",
            patchText: "diff --git a/apps/demo/src/App.tsx b/apps/demo/src/App.tsx",
            changedFiles: ["apps/demo/src/App.tsx"],
            stats: {
              filesChanged: 1,
              additions: 2,
              deletions: 1,
              files: [
                {
                  path: "apps/demo/src/App.tsx",
                  additions: 2,
                  deletions: 1,
                },
              ],
            },
          },
        ]),
        { status: 200 },
      )
    })

    const diffs = await listTaskRunDiffs("http://127.0.0.1:8000", "run-1", fetchMock)

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/task-runs/run-1/diffs",
      {
        cache: "no-store",
      },
    )
    expect(diffs[0].changedFiles).toEqual(["apps/demo/src/App.tsx"])
    expect(diffs[0].stats.additions).toBe(2)
  })
})
