import { describe, expect, it, vi } from "vitest"

import {
  approveTaskRun,
  createSessionMessage,
  createTaskRun,
  createPreviewDeployment,
  createTaskRunReview,
  createWorkspaceSession,
  denyTaskRun,
  forceCodexFailure,
  getSessionLedger,
  getBackendHealth,
  getDemoWorkspace,
  interruptTaskRun,
  listWorkspaceAgentProfiles,
  listWorkspaceAgents,
  listTaskRunDeployments,
  listTaskRunDiffs,
  listTaskRunPreviews,
  listTaskRunReviews,
  listSessionMessages,
  listSessionTasks,
  listWorkspaceSessions,
  retryTaskRun,
  retryTaskRunWithFallback,
  sessionEventsUrl,
  startTaskRunPreview,
  stopPreview,
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

  it("lists IM-style agent contacts for a workspace", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify([
          {
            id: "agent-frontend",
            displayName: "Frontend Agent",
            avatarInitials: "FE",
            role: "frontend",
            adapterType: "codex",
            capabilityTags: ["Vite React", "UI changes"],
            status: "available",
            safeForWrite: true,
            safeForReview: false,
            description: "Executes bounded frontend changes.",
            contactType: "agent",
          },
        ]),
        { status: 200 },
      )
    })

    const agents = await listWorkspaceAgents(
      "http://127.0.0.1:8000",
      "workspace-1",
      fetchMock,
    )

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/workspaces/workspace-1/agents",
      {
        cache: "no-store",
      },
    )
    expect(agents[0].displayName).toBe("Frontend Agent")
    expect(agents[0].capabilityTags).toContain("Vite React")
  })

  it("lists minimal agent profiles for a workspace", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify([
          {
            id: "agent-frontend",
            displayName: "Frontend Agent",
            avatarInitials: "FE",
            role: "frontend",
            adapterType: "codex",
            providerId: "local-codex-cli",
            capabilityTags: ["Vite React", "UI changes"],
            supportedRoles: ["frontend"],
            supportedTargets: ["demo-frontend", "external-frontend"],
            supportedModes: ["direct-assignment", "scheduled-task"],
            safeForWrite: true,
            safeForReview: false,
            description: "Executes bounded frontend changes.",
            status: "available",
          },
        ]),
        { status: 200 },
      )
    })

    const profiles = await listWorkspaceAgentProfiles(
      "http://127.0.0.1:8000",
      "workspace-1",
      fetchMock,
    )

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/workspaces/workspace-1/agent-profiles",
      {
        cache: "no-store",
      },
    )
    expect(profiles[0].providerId).toBe("local-codex-cli")
    expect(profiles[0].supportedRoles).toEqual(["frontend"])
    expect(profiles[0].supportedTargets).toContain("demo-frontend")
    expect(profiles[0].status).toBe("available")
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

  it("reads the session execution ledger", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          id: "ledger-1",
          sessionId: "session-1",
          currentGoal: "@orchestrator build a login page",
          activeAgents: ["orchestrator", "frontend"],
          latestTaskId: "task-1",
          latestTaskRunId: "run-1",
          latestDiffArtifactId: "artifact-diff-1",
          latestChangedFiles: ["apps/demo/src/App.tsx"],
          latestPreviewId: "preview-1",
          latestPreviewUrl: "http://127.0.0.1:4317",
          latestPreviewHealth: "healthy",
          latestDeploymentId: "deployment-1",
          latestDeploymentProvider: "mock",
          latestDeploymentStatus: "ready",
          lastSuccessfulAdapter: "scripted_mock",
          summaryMd: "Current goal: @orchestrator build a login page",
          updatedAt: "2026-05-21T00:00:00Z",
        }),
        { status: 200 },
      )
    })

    const ledger = await getSessionLedger(
      "http://127.0.0.1:8000",
      "session-1",
      fetchMock,
    )

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/sessions/session-1/ledger",
      {
        cache: "no-store",
      },
    )
    expect(ledger?.activeAgents).toEqual(["orchestrator", "frontend"])
    expect(ledger?.latestPreviewHealth).toBe("healthy")
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

  it("creates, interrupts, retries, approves, denies, and falls back task runs", async () => {
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
    await approveTaskRun("http://127.0.0.1:8000", "run-1", fetchMock)
    await denyTaskRun("http://127.0.0.1:8000", "run-1", "No thanks.", fetchMock)
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
      "http://127.0.0.1:8000/task-runs/run-1/approve",
      { method: "POST" },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://127.0.0.1:8000/task-runs/run-1/deny",
      {
        body: JSON.stringify({ reason: "No thanks." }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "http://127.0.0.1:8000/task-runs/run-1/retry-with-fallback",
      { method: "POST" },
    )
    expect(fallback.adapterType).toBe("scripted_mock")
  })

  it("creates a forced Codex failure run for demo recovery", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          id: "run-failed",
          taskId: "task-1",
          sessionId: "session-1",
          agentId: "agent-frontend",
          adapterType: "codex",
          adapterRunId: null,
          state: "failed",
          startedAt: null,
          endedAt: "2026-05-15T10:31:00Z",
          worktreePath: "/repo/.worktrees/session-1",
          baseRef: "abc123",
          headRef: null,
          errorCode: "CODEX_DEMO_FORCED_FAILURE",
          errorMessage: "Forced Codex failure requested for demo recovery.",
          metricsJson: { adapterType: "codex", forcedFailure: true },
          createdAt: "2026-05-15T10:30:00Z",
          updatedAt: "2026-05-15T10:31:00Z",
        }),
        { status: 201 },
      )
    })

    const run = await forceCodexFailure("http://127.0.0.1:8000", "task-1", fetchMock)

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/tasks/task-1/runs/force-codex-failure",
      { method: "POST" },
    )
    expect(run.errorCode).toBe("CODEX_DEMO_FORCED_FAILURE")
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

  it("creates and lists review artifacts for a task run", async () => {
    const reviewPayload = {
      id: "review-1",
      artifactId: "artifact-review-1",
      taskRunId: "run-1",
      reviewedDiffArtifactId: "artifact-diff-1",
      artifactType: "review",
      title: "Review Agent report",
      status: "passed",
      riskLevel: "low",
      summary: "Scripted Review Agent passed 1 changed file with low risk.",
      filesReviewed: ["apps/demo/src/App.tsx"],
      findings: [],
      suggestedChanges: [],
      adapterType: "scripted_mock",
    }
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString()
      if (url.endsWith("/reviews")) {
        return new Response(JSON.stringify([reviewPayload]), { status: 200 })
      }
      return new Response(JSON.stringify(reviewPayload), {
        status: init?.method === "POST" ? 201 : 200,
      })
    })

    const created = await createTaskRunReview(
      "http://127.0.0.1:8000",
      "run-1",
      fetchMock,
    )
    const reviews = await listTaskRunReviews(
      "http://127.0.0.1:8000",
      "run-1",
      fetchMock,
    )

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/task-runs/run-1/review",
      { method: "POST" },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/task-runs/run-1/reviews",
      { cache: "no-store" },
    )
    expect(created.status).toBe("passed")
    expect(reviews[0].adapterType).toBe("scripted_mock")
  })

  it("starts, lists, and stops preview artifacts for a task run", async () => {
    const previewPayload = {
      id: "preview-1",
      artifactId: "artifact-preview-1",
      taskRunId: "run-1",
      artifactType: "preview",
      title: "Vite React preview",
      status: "ready",
      port: 5173,
      url: "http://127.0.0.1:5173",
      command: "pnpm dev --host 127.0.0.1 --port 5173",
      processId: 4242,
      healthStatus: "healthy",
      statusReason: null,
      expiresAt: "2026-05-15T12:00:00Z",
      lastCheckedAt: "2026-05-15T10:30:00Z",
    }
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString()
      if (url.endsWith("/previews")) {
        return new Response(JSON.stringify([previewPayload]), { status: 200 })
      }
      return new Response(JSON.stringify(previewPayload), {
        status: init?.method === "POST" ? 201 : 200,
      })
    })

    const created = await startTaskRunPreview("http://127.0.0.1:8000", "run-1", fetchMock)
    const previews = await listTaskRunPreviews("http://127.0.0.1:8000", "run-1", fetchMock)
    const stopped = await stopPreview("http://127.0.0.1:8000", "preview-1", fetchMock)

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/task-runs/run-1/preview",
      { method: "POST" },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/task-runs/run-1/previews",
      { cache: "no-store" },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/previews/preview-1/stop",
      { method: "POST" },
    )
    expect(created.url).toBe("http://127.0.0.1:5173")
    expect(previews[0].healthStatus).toBe("healthy")
    expect(stopped.port).toBe(5173)
  })

  it("creates and lists mock deployment artifacts", async () => {
    const deploymentPayload = {
      id: "deployment-1",
      artifactId: "artifact-deploy-1",
      taskRunId: "run-1",
      artifactType: "deployment",
      title: "Mock deploy",
      status: "ready",
      provider: "mock",
      providerType: "mock",
      environment: "preview",
      commitSha: "def456+worktree",
      url: "https://mock.agenthub.local/deployments/deployment-1",
      deployLogUri: "mock://deployments/deployment-1/logs",
      targetId: "demo-frontend",
      sourcePreviewId: "preview-1",
      sourceDiffArtifactId: "artifact-diff-1",
      sourceReviewArtifactId: "artifact-review-1",
      logs: ["Mock deploy accepted healthy preview preview-1."],
      statusHistory: [{ status: "ready", message: "Mock deployment is ready." }],
      createdAt: "2026-05-15T10:30:00Z",
      updatedAt: "2026-05-15T10:30:00Z",
    }
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString()
      if (url.endsWith("/deployments")) {
        return new Response(JSON.stringify([deploymentPayload]), { status: 200 })
      }
      return new Response(JSON.stringify(deploymentPayload), {
        status: init?.method === "POST" ? 201 : 200,
      })
    })

    const created = await createPreviewDeployment(
      "http://127.0.0.1:8000",
      "preview-1",
      fetchMock,
    )
    const deployments = await listTaskRunDeployments(
      "http://127.0.0.1:8000",
      "run-1",
      fetchMock,
    )

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/previews/preview-1/deploy",
      { method: "POST" },
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/task-runs/run-1/deployments",
      { cache: "no-store" },
    )
    expect(created.provider).toBe("mock")
    expect(deployments[0].deployLogUri).toBe("mock://deployments/deployment-1/logs")
  })
})
