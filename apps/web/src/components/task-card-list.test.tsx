import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { createElement } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { TaskCardList } from "./task-card-list"
import { sampleDeploymentArtifact } from "./__fixtures__/sample-deployment"
import { sampleDiffArtifact } from "./__fixtures__/sample-diff"
import { samplePreviewArtifact } from "./__fixtures__/sample-preview"
import { sampleReviewArtifact } from "./__fixtures__/sample-review"
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
    expect(screen.getByText("任务 1")).toBeTruthy()
    expect(screen.getByText("@frontend")).toBeTruthy()
    expect(screen.getByText("待处理")).toBeTruthy()
    expect(screen.getByText("依赖 task-0")).toBeTruthy()
  })

  it("renders scheduler dependency, lock, retry, and fallback state metadata", () => {
    const waitingLockTask: SessionTask = {
      ...baseTask,
      status: "waiting_target_lock",
      planJson: {
        scheduler: {
          state: "waiting_target_lock",
          runnable: false,
          reason: "Waiting for target write lock: demo-frontend.",
          dependencyIds: ["task-0"],
          blockingDependencyIds: [],
          targetId: "demo-frontend",
          writeLockRequired: true,
          lockHolderTaskRunIds: ["run-lock-holder"],
          retryable: true,
          fallbackAvailable: true,
        },
      },
    }

    render(createElement(TaskCardList, { tasks: [waitingLockTask] }))

    expect(screen.getAllByText("等待目标锁").length).toBeGreaterThan(0)
    expect(screen.getByText("调度状态")).toBeTruthy()
    expect(screen.getByText("demo-frontend")).toBeTruthy()
    expect(screen.getByText("Waiting for target write lock: demo-frontend.")).toBeTruthy()
    expect(screen.getByText("锁持有者 run-lock")).toBeTruthy()
    expect(screen.getByText("写锁")).toBeTruthy()
    expect(screen.getByText("fallback available")).toBeTruthy()
    expect(screen.getByText("retryable")).toBeTruthy()
  })

  it("renders read-only planner rationale and task review metadata", () => {
    const plannedTask: SessionTask = {
      ...baseTask,
      planJson: {
        plannerEvidence: {
          errorCode: "LLM_TASK_PLAN_VALIDATION_FAILED",
          errorSummary: "targetId was invalid before deterministic fallback.",
          fallbackReason: "non_task_coding_outcome",
          plannerSource: "fallback",
          providerId: "deepseek-api-planner",
          validationResult: "failed",
        },
      },
      planReviewMetadata: {
        plannerMode: "llm_v1",
        rationale: "Implement a game inside the registered frontend target.",
        assignedRole: "frontend",
        targetId: "demo-frontend",
        plannedFiles: ["apps/demo/src/App.tsx", "apps/demo/src/game/Breakout.tsx"],
        acceptanceCriteria: ["Keyboard controls work", "Score updates"],
        validationExpectations: ["pnpm build"],
        taskBreakdown: [
          {
            title: "Build Breakout",
            role: "frontend",
            targetId: "demo-frontend",
            plannedFiles: ["apps/demo/src/game/Breakout.tsx"],
          },
        ],
        readOnly: true,
      },
    }

    render(createElement(TaskCardList, { tasks: [plannedTask] }))

    expect(screen.getByText("计划审阅")).toBeTruthy()
    expect(screen.getByText("llm_v1")).toBeTruthy()
    expect(screen.getAllByText("demo-frontend").length).toBeGreaterThan(0)
    expect(
      screen.getByText("Implement a game inside the registered frontend target."),
    ).toBeTruthy()
    expect(screen.getByText("apps/demo/src/game/Breakout.tsx")).toBeTruthy()
    expect(screen.getByText("task graph 1")).toBeTruthy()
    expect(screen.getByText("acceptance 2")).toBeTruthy()
    expect(screen.getByText("validation 1")).toBeTruthy()
    expect(screen.getByText("read-only")).toBeTruthy()
    expect(screen.getByText("规划证据")).toBeTruthy()
    expect(screen.getByText("fallback")).toBeTruthy()
    expect(screen.getByText("deepseek-api-planner")).toBeTruthy()
    expect(screen.getByText("validation failed")).toBeTruthy()
    expect(screen.getByText("fallback non_task_coding_outcome")).toBeTruthy()
    expect(screen.getByText("LLM_TASK_PLAN_VALIDATION_FAILED")).toBeTruthy()
    expect(screen.getByText("targetId was invalid before deterministic fallback.")).toBeTruthy()
  })

  it("renders PMO plan decision actions for pending reviewed plans", () => {
    const onApprovePlan = vi.fn()
    const onRejectPlan = vi.fn()
    const onRequestClarification = vi.fn()
    const reviewedTask: SessionTask = {
      ...baseTask,
      planJson: {
        pmoDecision: {
          state: "pending_review",
          actor: "orchestrator",
          reason: "需要用户确认后再执行。",
          nextActionSummary: "Review the plan and approve, reject, or request clarification.",
        },
      },
    }

    render(
      createElement(TaskCardList, {
        tasks: [reviewedTask],
        onApprovePlan,
        onRejectPlan,
        onRequestClarification,
      }),
    )

    expect(screen.getByText("PMO 决策")).toBeTruthy()
    expect(screen.getByText("待审阅")).toBeTruthy()
    expect(screen.getByText("需要用户确认后再执行。")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "批准计划" }))
    fireEvent.click(screen.getByRole("button", { name: "拒绝计划" }))
    fireEvent.click(screen.getByRole("button", { name: "要求澄清" }))

    expect(onApprovePlan).toHaveBeenCalledWith("task-1")
    expect(onRejectPlan).toHaveBeenCalledWith("task-1")
    expect(onRequestClarification).toHaveBeenCalledWith("task-1")
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

    expect(screen.getAllByText("第 1 次").length).toBeGreaterThan(0)
    expect(screen.getAllByText("codex").length).toBeGreaterThan(0)
    expect(screen.getAllByText("失败").length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole("button", { name: "开始运行" }))
    fireEvent.click(screen.getByRole("button", { name: "模拟 Codex 失败" }))
    fireEvent.click(screen.getByRole("button", { name: "重试" }))
    fireEvent.click(screen.getByRole("button", { name: "使用兜底重试" }))
    fireEvent.click(screen.getByRole("button", { name: "中断" }))

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

    expect(screen.getByText("需要审批")).toBeTruthy()
    expect(screen.getByText("continue scripted mock run")).toBeTruthy()
    expect(screen.getByText("product_confirmation")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "批准" }))
    fireEvent.click(screen.getByRole("button", { name: "拒绝" }))

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

    expect(screen.getByText("已恢复")).toBeTruthy()
    expect(screen.getByText("第 1 次")).toBeTruthy()
    expect(screen.getByText("第 2 次")).toBeTruthy()
    expect(screen.getByText("scripted_mock")).toBeTruthy()
    expect(screen.getByText("CODEX_DEMO_FORCED_FAILURE")).toBeTruthy()
  })

  it("loads diff artifacts as timeline summary chips and panel items", async () => {
    const onArtifactsChange = vi.fn()
    const onSelectArtifact = vi.fn()
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      if (
        url.endsWith("/previews") ||
        url.endsWith("/reviews") ||
        url.endsWith("/deployments")
      ) {
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
        onArtifactsChange,
        onSelectArtifact,
        tasks: [completedTask],
      }),
    )

    expect(await screen.findByText(/Diff 就绪/)).toBeTruthy()
    expect(screen.getByText("已变更：apps/demo/src/App.tsx")).toBeTruthy()
    expect(screen.queryByText("Git Diff")).toBeNull()
    fireEvent.click(screen.getByText(/Diff 就绪/))
    expect(onSelectArtifact).toHaveBeenCalledWith(`diff:${sampleDiffArtifact.id}`)
    await waitFor(() =>
      expect(onArtifactsChange).toHaveBeenLastCalledWith([
        expect.objectContaining({
          artifact: sampleDiffArtifact,
          id: `diff:${sampleDiffArtifact.id}`,
          kind: "diff",
        }),
      ]),
    )
    expect(fetcher).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/task-runs/run-1/diffs",
      {
        cache: "no-store",
      },
    )
  })

  it("loads previews as timeline summary chips and still starts preview runs", async () => {
    const onArtifactsChange = vi.fn()
    const onSelectArtifact = vi.fn()
    const onStartPreview = vi.fn()
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      if (
        url.endsWith("/diffs") ||
        url.endsWith("/reviews") ||
        url.endsWith("/deployments")
      ) {
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
        onArtifactsChange,
        onSelectArtifact,
        onStartPreview,
        tasks: [completedTask],
      }),
    )

    expect(await screen.findByText("预览健康")).toBeTruthy()
    expect(screen.queryByText("Vite React 预览")).toBeNull()
    fireEvent.click(screen.getByText("预览健康"))
    fireEvent.click(screen.getByRole("button", { name: "启动预览" }))

    expect(onSelectArtifact).toHaveBeenCalledWith(`preview:${samplePreviewArtifact.id}`)
    expect(onStartPreview).toHaveBeenCalledWith("run-1")
    await waitFor(() =>
      expect(onArtifactsChange).toHaveBeenLastCalledWith([
        expect.objectContaining({
          artifact: samplePreviewArtifact,
          id: `preview:${samplePreviewArtifact.id}`,
          kind: "preview",
        }),
      ]),
    )
  })

  it("loads deployments as timeline summary chips and panel items", async () => {
    const onArtifactsChange = vi.fn()
    const onSelectArtifact = vi.fn()
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
        onArtifactsChange,
        onSelectArtifact,
        tasks: [completedTask],
      }),
    )

    expect(await screen.findByText("模拟部署就绪")).toBeTruthy()
    expect(
      screen.getByText("https://mock.agenthub.local/deployments/deployment-1"),
    ).toBeTruthy()
    fireEvent.click(screen.getByText("模拟部署就绪"))
    expect(onSelectArtifact).toHaveBeenCalledWith(
      `deployment:${sampleDeploymentArtifact.id}`,
    )
    await waitFor(() =>
      expect(onArtifactsChange).toHaveBeenLastCalledWith([
        expect.objectContaining({
          artifact: sampleDeploymentArtifact,
          id: `deployment:${sampleDeploymentArtifact.id}`,
          kind: "deployment",
        }),
      ]),
    )
    expect(fetcher).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/task-runs/run-1/deployments",
      {
        cache: "no-store",
      },
    )
  })

  it("loads review artifacts as non-blocking timeline chips and panel items", async () => {
    const onArtifactsChange = vi.fn()
    const onSelectArtifact = vi.fn()
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      if (url.endsWith("/reviews")) {
        return new Response(JSON.stringify([sampleReviewArtifact]), { status: 200 })
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
        onArtifactsChange,
        onSelectArtifact,
        tasks: [completedTask],
      }),
    )

    expect(await screen.findByText("评审通过")).toBeTruthy()
    fireEvent.click(screen.getByText("评审通过"))
    expect(onSelectArtifact).toHaveBeenCalledWith(`review:${sampleReviewArtifact.id}`)
    await waitFor(() =>
      expect(onArtifactsChange).toHaveBeenLastCalledWith([
        expect.objectContaining({
          artifact: sampleReviewArtifact,
          id: `review:${sampleReviewArtifact.id}`,
          kind: "review",
        }),
      ]),
    )
    expect(fetcher).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/task-runs/run-1/reviews",
      {
        cache: "no-store",
      },
    )
  })

  it("renders a multi-agent execution trace with artifact links and warning states", async () => {
    const onSelectArtifact = vi.fn()
    const warningReview = {
      ...sampleReviewArtifact,
      riskLevel: "medium",
      status: "warning",
      summary: "Review Agent found a non-blocking caveat.",
    }
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      if (url.endsWith("/diffs")) {
        return new Response(JSON.stringify([sampleDiffArtifact]), { status: 200 })
      }
      if (url.endsWith("/reviews")) {
        return new Response(JSON.stringify([warningReview]), { status: 200 })
      }
      if (url.endsWith("/previews")) {
        return new Response(JSON.stringify([samplePreviewArtifact]), { status: 200 })
      }
      if (url.endsWith("/deployments")) {
        return new Response(JSON.stringify([sampleDeploymentArtifact]), { status: 200 })
      }
      return new Response(JSON.stringify([]), { status: 200 })
    })
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
          id: "run-1",
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

    render(
      createElement(TaskCardList, {
        artifactRefreshKey: 1,
        backendUrl: "http://127.0.0.1:8000",
        fetcher,
        onSelectArtifact,
        tasks: [recoveredTask],
      }),
    )

    expect(await screen.findByText("Diff produced")).toBeTruthy()
    expect(screen.getByText("Manager planned")).toBeTruthy()
    expect(screen.getByText("Coding Agent ran")).toBeTruthy()
    expect(screen.getByText("Review Agent reviewed")).toBeTruthy()
    expect(screen.getByText("Preview healthy")).toBeTruthy()
    expect(screen.getAllByText("Mock deploy ready").length).toBeGreaterThan(0)
    expect(screen.getByText("Fallback")).toBeTruthy()
    expect(screen.getByText("Review warning")).toBeTruthy()
    expect(
      screen.getAllByText("Review Agent found a non-blocking caveat.").length,
    ).toBeGreaterThan(0)
    expect(screen.getByText("Diff Service · git diff service")).toBeTruthy()
    expect(screen.getByText("Preview Service · Vite preview service")).toBeTruthy()
    expect(screen.getByText("Mock Deploy Service · mock")).toBeTruthy()

    const artifactButtons = screen.getAllByRole("button", { name: "查看产物" })
    fireEvent.click(artifactButtons[0])
    fireEvent.click(artifactButtons[1])
    fireEvent.click(artifactButtons[2])
    fireEvent.click(artifactButtons[3])

    expect(onSelectArtifact).toHaveBeenNthCalledWith(1, `diff:${sampleDiffArtifact.id}`)
    expect(onSelectArtifact).toHaveBeenNthCalledWith(2, `review:${warningReview.id}`)
    expect(onSelectArtifact).toHaveBeenNthCalledWith(
      3,
      `preview:${samplePreviewArtifact.id}`,
    )
    expect(onSelectArtifact).toHaveBeenNthCalledWith(
      4,
      `deployment:${sampleDeploymentArtifact.id}`,
    )
  })

  it("renders artifact message cards and maps actions to existing panel/context APIs", async () => {
    const onOpenPreview = vi.fn()
    const onSelectArtifact = vi.fn()
    const onUseArtifactContext = vi.fn()
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      if (url.endsWith("/diffs")) {
        return new Response(JSON.stringify([sampleDiffArtifact]), { status: 200 })
      }
      if (url.endsWith("/reviews")) {
        return new Response(JSON.stringify([sampleReviewArtifact]), { status: 200 })
      }
      if (url.endsWith("/previews")) {
        return new Response(JSON.stringify([samplePreviewArtifact]), { status: 200 })
      }
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
        onOpenPreview,
        onSelectArtifact,
        onUseArtifactContext,
        tasks: [completedTask],
      }),
    )

    expect(await screen.findByText("证据卡片")).toBeTruthy()
    expect(screen.getByText("4 个会话产物")).toBeTruthy()
    expect(
      screen.getByText("本地部署证据卡片，不代表生产发布。"),
    ).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "查看 Diff" }))
    fireEvent.click(screen.getAllByRole("button", { name: "作为上下文" })[0])
    fireEvent.click(screen.getByRole("button", { name: "查看评审" }))
    fireEvent.click(screen.getByRole("button", { name: "打开预览" }))
    fireEvent.click(screen.getByRole("button", { name: "查看部署" }))
    fireEvent.click(screen.getAllByRole("button", { name: "作为上下文" })[2])
    fireEvent.click(screen.getAllByRole("button", { name: "询问此项" })[0])
    fireEvent.click(screen.getAllByRole("button", { name: "基于此修改" })[0])
    fireEvent.click(screen.getAllByRole("button", { name: "交给 Agent" })[2])

    expect(onSelectArtifact).toHaveBeenNthCalledWith(1, `diff:${sampleDiffArtifact.id}`)
    expect(onUseArtifactContext).toHaveBeenCalledWith(
      expect.objectContaining({
        id: `diff:${sampleDiffArtifact.id}`,
        kind: "diff",
      }),
    )
    expect(onSelectArtifact).toHaveBeenNthCalledWith(
      2,
      `review:${sampleReviewArtifact.id}`,
    )
    expect(onOpenPreview).toHaveBeenCalledWith(samplePreviewArtifact)
    expect(onSelectArtifact).toHaveBeenNthCalledWith(
      3,
      `deployment:${sampleDeploymentArtifact.id}`,
    )
    expect(onUseArtifactContext).toHaveBeenCalledWith(
      expect.objectContaining({
        id: `deployment:${sampleDeploymentArtifact.id}`,
        kind: "deployment",
      }),
    )
    expect(onUseArtifactContext).toHaveBeenCalledWith(
      expect.objectContaining({
        id: `diff:${sampleDiffArtifact.id}`,
        kind: "diff",
      }),
      "ask",
    )
    expect(onUseArtifactContext).toHaveBeenCalledWith(
      expect.objectContaining({
        id: `diff:${sampleDiffArtifact.id}`,
        kind: "diff",
      }),
      "revise",
    )
    expect(onUseArtifactContext).toHaveBeenCalledWith(
      expect.objectContaining({
        id: `deployment:${sampleDeploymentArtifact.id}`,
        kind: "deployment",
      }),
      "send_to_agent",
    )
  })

  it("offers review and mock deploy card actions only when backed by existing APIs", async () => {
    const onCreateDeploy = vi.fn()
    const onCreateReview = vi.fn()
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString()
      if (url.endsWith("/diffs")) {
        return new Response(JSON.stringify([sampleDiffArtifact]), { status: 200 })
      }
      if (url.endsWith("/previews")) {
        return new Response(JSON.stringify([samplePreviewArtifact]), { status: 200 })
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
        onCreateDeploy,
        onCreateReview,
        tasks: [completedTask],
      }),
    )

    expect(await screen.findByText("证据卡片")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "评审 Diff" }))
    fireEvent.click(screen.getByRole("button", { name: "创建部署卡" }))

    expect(onCreateReview).toHaveBeenCalledWith("run-1")
    expect(onCreateDeploy).toHaveBeenCalledWith(samplePreviewArtifact.id)
  })
})
