import { render, screen } from "@testing-library/react"
import { createElement } from "react"
import { describe, expect, it } from "vitest"

import { MissionPanel } from "./mission-panel"
import type { SessionExecutionLedger, SessionTask, WorkspaceSession } from "@/lib/api"

const ledger: SessionExecutionLedger = {
  activeAgents: ["orchestrator", "frontend"],
  currentGoal: "实现图书管理系统",
  id: "ledger-1",
  lastSuccessfulAdapter: "codex",
  latestChangedFiles: ["src/App.tsx"],
  latestDeploymentId: null,
  latestDeploymentProvider: null,
  latestDeploymentStatus: null,
  latestDiffArtifactId: "diff-1",
  latestPreviewHealth: "healthy",
  latestPreviewId: "preview-1",
  latestPreviewUrl: "http://127.0.0.1:4173",
  latestTaskId: "task-ready",
  latestTaskRunId: "run-1",
  sessionId: "session-1",
  summaryMd: "Current goal",
  updatedAt: "2026-06-08T00:00:00Z",
}

const selectedSession: WorkspaceSession = {
  activeBackendTargetId: "demo-backend",
  activeFrontendTargetId: "demo-frontend",
  boundBranch: "main",
  createdAt: "2026-06-08T00:00:00Z",
  id: "session-1",
  lastMessageAt: "2026-06-08T00:00:00Z",
  memorySnapshotId: "memory-snapshot-123",
  sessionType: "group",
  status: "active",
  title: "PMO session",
  updatedAt: "2026-06-08T00:00:00Z",
  workspaceId: "workspace-1",
  worktreePath: ".worktrees/session",
}

const tasks: SessionTask[] = [
  {
    assignedAgentId: "agent-frontend",
    assignedAgentRole: "frontend",
    createdAt: "2026-06-08T00:00:00Z",
    createdByMessageId: "message-1",
    dependsOnTaskIds: [],
    id: "task-ready",
    intentType: "frontend_change",
    planJson: { scheduler: { state: "ready" } },
    priority: 1,
    sessionId: "session-1",
    status: "pending",
    taskRuns: [
      {
        adapterRunId: null,
        adapterType: "codex",
        agentId: "agent-frontend",
        approvalRequest: null,
        baseRef: null,
        createdAt: "2026-06-08T00:00:00Z",
        endedAt: null,
        errorCode: null,
        errorMessage: null,
        headRef: null,
        id: "run-1",
        metricsJson: {
          providerGateway: {
            health: { providerId: "local-codex-cli", status: "healthy" },
            resolution: { selectedProviderId: "local-codex-cli" },
          },
        },
        previewDeployJobs: [{ state: "completed" }],
        sessionId: "session-1",
        sessionQueue: { state: "running" },
        startedAt: "2026-06-08T00:00:00Z",
        state: "streaming",
        targetLock: { state: "held" },
        taskId: "task-ready",
        updatedAt: "2026-06-08T00:00:00Z",
        worktreePath: ".worktrees/session",
      },
    ],
    title: "Ready task",
    updatedAt: "2026-06-08T00:00:00Z",
  },
  {
    assignedAgentId: "agent-review",
    assignedAgentRole: "review",
    createdAt: "2026-06-08T00:00:00Z",
    createdByMessageId: "message-1",
    dependsOnTaskIds: ["task-ready"],
    id: "task-waiting",
    intentType: "review",
    planJson: {
      scheduler: {
        state: "waiting_dependency",
        reason: "Waiting for upstream dependencies to complete.",
      },
    },
    priority: 2,
    sessionId: "session-1",
    status: "waiting_dependency",
    taskRuns: [],
    title: "Waiting task",
    updatedAt: "2026-06-08T00:00:00Z",
  },
]

describe("MissionPanel", () => {
  it("summarizes PMO readiness and next actions from current tasks", () => {
    render(createElement(MissionPanel, { ledger, selectedSession, tasks }))

    expect(screen.getByText("PMO 状态")).toBeTruthy()
    expect(screen.getByText("ready 1")).toBeTruthy()
    expect(screen.getByText("waiting 1")).toBeTruthy()
    expect(screen.getByText("建议")).toBeTruthy()
    expect(screen.getByText("启动可运行任务")).toBeTruthy()
    expect(screen.getByText("检查阻塞任务")).toBeTruthy()
    expect(screen.getByText("provider local-codex-cli:healthy / queue running / lock held / job completed")).toBeTruthy()
  })
})
