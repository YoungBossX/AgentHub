import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { createElement } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { TaskCardList } from "./task-card-list"
import { sampleDeploymentArtifact } from "./__fixtures__/sample-deployment"
import { sampleDiffArtifact } from "./__fixtures__/sample-diff"
import { samplePreviewArtifact } from "./__fixtures__/sample-preview"
import type { SessionTask } from "@/lib/api"

vi.mock("@monaco-editor/react", () => ({
  DiffEditor: () => <div data-testid="monaco-diff-editor" />,
}))

afterEach(() => cleanup())

const baseTask: SessionTask = {
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
  taskRuns: [],
  createdAt: "2026-05-14T00:00:00Z",
  updatedAt: "2026-05-14T00:00:00Z",
}

describe("TaskCardList", () => {
  it("renders task titles, assigned agents, statuses, and dependencies", () => {
    render(createElement(TaskCardList, { tasks: [baseTask] }))

    expect(screen.getByText("Build the Vite React login page")).toBeTruthy()
    expect(screen.getByText("Step 1 · frontend")).toBeTruthy()
    expect(screen.getByText("pending")).toBeTruthy()
    expect(screen.getByText("Depends on task-0")).toBeTruthy()
  })

  it("renders run history and P0 run controls", () => {
    const onCreateRun = vi.fn()
    const onForceCodexFailure = vi.fn()
    const onInterruptRun = vi.fn()
    const onRetryRun = vi.fn()
    const onRetryWithFallback = vi.fn()
    const failedTask: SessionTask = {
      ...baseTask,
      id: "task-failed",
      status: "failed",
      taskRuns: [
        {
          id: "run-1",
          taskId: "task-failed",
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
    }
    const streamingTask: SessionTask = {
      ...baseTask,
      id: "task-2",
      status: "running",
      taskRuns: [
        {
          ...failedTask.taskRuns[0],
          id: "run-2",
          taskId: "task-2",
          state: "streaming",
          errorCode: null,
          errorMessage: null,
        },
      ],
    }

    render(
      createElement(TaskCardList, {
        tasks: [baseTask, failedTask, streamingTask],
        onCreateRun,
        onForceCodexFailure,
        onInterruptRun,
        onRetryRun,
        onRetryWithFallback,
      }),
    )

    expect(screen.getByText("Run 1 · codex · failed")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Start run" }))
    fireEvent.click(screen.getByRole("button", { name: "Force Codex failure" }))
    fireEvent.click(screen.getByRole("button", { name: "Retry" }))
    fireEvent.click(screen.getByRole("button", { name: "Retry with ScriptedMockAdapter" }))
    fireEvent.click(screen.getByRole("button", { name: "Interrupt" }))

    expect(onCreateRun).toHaveBeenCalledWith("task-1")
    expect(onForceCodexFailure).toHaveBeenCalledWith("task-1")
    expect(onRetryRun).toHaveBeenCalledWith("run-1")
    expect(onRetryWithFallback).toHaveBeenCalledWith("run-1")
    expect(onInterruptRun).toHaveBeenCalledWith("run-2")
  })

  it("renders an approval card for waiting approval runs", () => {
    const onApproveRun = vi.fn()
    const onDenyRun = vi.fn()
    const approvalTask: SessionTask = {
      ...baseTask,
      status: "waiting_approval",
      taskRuns: [
        {
          id: "run-approval",
          taskId: "task-1",
          sessionId: "session-1",
          agentId: "agent-frontend",
          adapterType: "scripted_mock",
          adapterRunId: "scripted-mock-approval",
          state: "waiting_approval",
          startedAt: "2026-05-15T10:30:00Z",
          endedAt: null,
          worktreePath: "/repo/.worktrees/session-1",
          baseRef: "abc123",
          headRef: null,
          errorCode: null,
          errorMessage: null,
          metricsJson: { adapterType: "scripted_mock" },
          approvalRequest: {
            approvalType: "product_confirmation",
            reason: "Scripted mock approval simulation requested.",
            requestedAction: "continue scripted mock run",
            riskLevel: "medium",
            command: null,
            path: null,
            expiresAt: null,
          },
          createdAt: "2026-05-15T10:30:00Z",
          updatedAt: "2026-05-15T10:31:00Z",
        },
      ],
    }

    render(
      createElement(TaskCardList, {
        tasks: [approvalTask],
        onApproveRun,
        onDenyRun,
      }),
    )

    expect(screen.getByText("Approval required")).toBeTruthy()
    expect(screen.getByText("continue scripted mock run")).toBeTruthy()
    expect(screen.getByText("product_confirmation")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Approve" }))
    fireEvent.click(screen.getByRole("button", { name: "Deny" }))

    expect(onApproveRun).toHaveBeenCalledWith("run-approval")
    expect(onDenyRun).toHaveBeenCalledWith("run-approval")
  })

  it("keeps a failed Codex run and successful fallback run visible", () => {
    const recoveredTask: SessionTask = {
      ...baseTask,
      status: "completed",
      taskRuns: [
        {
          id: "run-failed",
          taskId: "task-1",
          sessionId: "session-1",
          agentId: "agent-frontend",
          adapterType: "codex",
          adapterRunId: null,
          state: "failed",
          startedAt: "2026-05-15T10:30:00Z",
          endedAt: "2026-05-15T10:31:00Z",
          worktreePath: "/repo/.worktrees/session-1",
          baseRef: "abc123",
          headRef: null,
          errorCode: "CODEX_DEMO_FORCED_FAILURE",
          errorMessage: "Forced Codex failure requested for demo recovery.",
          metricsJson: { adapterType: "codex", forcedFailure: true },
          createdAt: "2026-05-15T10:30:00Z",
          updatedAt: "2026-05-15T10:31:00Z",
        },
        {
          id: "run-fallback",
          taskId: "task-1",
          sessionId: "session-1",
          agentId: "agent-frontend",
          adapterType: "scripted_mock",
          adapterRunId: "scripted-mock-1",
          state: "completed",
          startedAt: "2026-05-15T10:32:00Z",
          endedAt: "2026-05-15T10:33:00Z",
          worktreePath: "/repo/.worktrees/session-1",
          baseRef: "abc123",
          headRef: "def456+worktree",
          errorCode: null,
          errorMessage: null,
          metricsJson: {
            adapterType: "scripted_mock",
            fallbackFromRunId: "run-failed",
            retryOfRunId: "run-failed",
          },
          createdAt: "2026-05-15T10:32:00Z",
          updatedAt: "2026-05-15T10:33:00Z",
        },
      ],
    }

    render(createElement(TaskCardList, { tasks: [recoveredTask] }))

    expect(screen.getByText("Run 1 · codex · failed")).toBeTruthy()
    expect(screen.getByText("Run 2 · scripted_mock · completed")).toBeTruthy()
    expect(screen.getByText("CODEX_DEMO_FORCED_FAILURE")).toBeTruthy()
  })

  it("loads and renders diff cards for task run history", async () => {
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      if (url.endsWith("/previews") || url.endsWith("/deployments")) {
        return new Response(JSON.stringify([]), { status: 200 })
      }
      return new Response(JSON.stringify([sampleDiffArtifact]), { status: 200 })
    })
    const completedTask: SessionTask = {
      ...baseTask,
      status: "completed",
      taskRuns: [
        {
          id: "run-1",
          taskId: "task-1",
          sessionId: "session-1",
          agentId: "agent-frontend",
          adapterType: "scripted_mock",
          adapterRunId: null,
          state: "completed",
          startedAt: "2026-05-14T00:00:00Z",
          endedAt: "2026-05-14T00:00:01Z",
          worktreePath: "/repo/.worktrees/session-1",
          baseRef: "abc123",
          headRef: "def456+worktree",
          errorCode: null,
          errorMessage: null,
          metricsJson: { adapterType: "scripted_mock" },
          createdAt: "2026-05-14T00:00:00Z",
          updatedAt: "2026-05-14T00:00:01Z",
        },
      ],
    }

    render(
      createElement(TaskCardList, {
        artifactRefreshKey: 1,
        backendUrl: "http://127.0.0.1:8000",
        fetcher,
        tasks: [completedTask],
      }),
    )

    expect(await screen.findByText("Git diff")).toBeTruthy()
    expect(screen.getByText("apps/demo/src/App.tsx")).toBeTruthy()
    expect(fetcher).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/task-runs/run-1/diffs",
      {
        cache: "no-store",
      },
    )
  })

  it("loads previews and starts a preview from task run history", async () => {
    const onCreateDeploy = vi.fn()
    const onOpenPreview = vi.fn()
    const onStartPreview = vi.fn()
    const onRefreshPreviews = vi.fn()
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      if (url.endsWith("/diffs") || url.endsWith("/deployments")) {
        return new Response(JSON.stringify([]), { status: 200 })
      }
      return new Response(JSON.stringify([samplePreviewArtifact]), { status: 200 })
    })
    const completedTask: SessionTask = {
      ...baseTask,
      status: "completed",
      taskRuns: [
        {
          id: "run-1",
          taskId: "task-1",
          sessionId: "session-1",
          agentId: "agent-frontend",
          adapterType: "scripted_mock",
          adapterRunId: null,
          state: "completed",
          startedAt: "2026-05-14T00:00:00Z",
          endedAt: "2026-05-14T00:00:01Z",
          worktreePath: "/repo/.worktrees/session-1",
          baseRef: "abc123",
          headRef: "def456+worktree",
          errorCode: null,
          errorMessage: null,
          metricsJson: { adapterType: "scripted_mock" },
          createdAt: "2026-05-14T00:00:00Z",
          updatedAt: "2026-05-14T00:00:01Z",
        },
      ],
    }

    render(
      createElement(TaskCardList, {
        artifactRefreshKey: 1,
        backendUrl: "http://127.0.0.1:8000",
        fetcher,
        onCreateDeploy,
        onOpenPreview,
        onRefreshPreviews,
        onStartPreview,
        tasks: [completedTask],
      }),
    )

    expect(await screen.findByText("Vite React preview")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Open preview" }))
    fireEvent.click(screen.getByRole("button", { name: "Refresh preview" }))
    fireEvent.click(screen.getByRole("button", { name: "Create deploy card" }))
    fireEvent.click(screen.getByRole("button", { name: "Start preview" }))

    expect(onOpenPreview).toHaveBeenCalledWith(samplePreviewArtifact)
    expect(onRefreshPreviews).toHaveBeenCalledWith("run-1")
    expect(onCreateDeploy).toHaveBeenCalledWith("preview-1")
    expect(onStartPreview).toHaveBeenCalledWith("run-1")
  })

  it("loads and renders deployment cards for task run history", async () => {
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      if (url.endsWith("/deployments")) {
        return new Response(JSON.stringify([sampleDeploymentArtifact]), { status: 200 })
      }
      return new Response(JSON.stringify([]), { status: 200 })
    })
    const completedTask: SessionTask = {
      ...baseTask,
      status: "completed",
      taskRuns: [
        {
          id: "run-1",
          taskId: "task-1",
          sessionId: "session-1",
          agentId: "agent-frontend",
          adapterType: "scripted_mock",
          adapterRunId: null,
          state: "completed",
          startedAt: "2026-05-14T00:00:00Z",
          endedAt: "2026-05-14T00:00:01Z",
          worktreePath: "/repo/.worktrees/session-1",
          baseRef: "abc123",
          headRef: "def456+worktree",
          errorCode: null,
          errorMessage: null,
          metricsJson: { adapterType: "scripted_mock" },
          createdAt: "2026-05-14T00:00:00Z",
          updatedAt: "2026-05-14T00:00:01Z",
        },
      ],
    }

    render(
      createElement(TaskCardList, {
        artifactRefreshKey: 1,
        backendUrl: "http://127.0.0.1:8000",
        fetcher,
        tasks: [completedTask],
      }),
    )

    expect(await screen.findByText("Mock deploy")).toBeTruthy()
    expect(screen.getByText("https://mock.agenthub.local/deployments/deployment-1")).toBeTruthy()
    expect(fetcher).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/task-runs/run-1/deployments",
      {
        cache: "no-store",
      },
    )
  })
})
