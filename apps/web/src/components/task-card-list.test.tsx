import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { createElement } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { TaskCardList } from "./task-card-list"
import { sampleDiffArtifact } from "./__fixtures__/sample-diff"
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
        onInterruptRun,
        onRetryRun,
        onRetryWithFallback,
      }),
    )

    expect(screen.getByText("Run 1 · codex · failed")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Start run" }))
    fireEvent.click(screen.getByRole("button", { name: "Retry" }))
    fireEvent.click(screen.getByRole("button", { name: "Retry with fallback" }))
    fireEvent.click(screen.getByRole("button", { name: "Interrupt" }))

    expect(onCreateRun).toHaveBeenCalledWith("task-1")
    expect(onRetryRun).toHaveBeenCalledWith("run-1")
    expect(onRetryWithFallback).toHaveBeenCalledWith("run-1")
    expect(onInterruptRun).toHaveBeenCalledWith("run-2")
  })

  it("loads and renders diff cards for task run history", async () => {
    const fetcher = vi.fn(async () => {
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
})
