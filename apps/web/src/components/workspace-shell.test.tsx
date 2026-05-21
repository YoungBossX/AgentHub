import { cleanup, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { WorkspaceShell } from "./workspace-shell"

const navigationMocks = vi.hoisted(() => ({
  replace: vi.fn(),
}))

const apiMocks = vi.hoisted(() => ({
  approveTaskRun: vi.fn(),
  createPreviewDeployment: vi.fn(),
  createSessionMessage: vi.fn(),
  createTaskRun: vi.fn(),
  createWorkspaceSession: vi.fn(),
  denyTaskRun: vi.fn(),
  forceCodexFailure: vi.fn(),
  getSessionLedger: vi.fn(),
  interruptTaskRun: vi.fn(),
  listSessionMessages: vi.fn(),
  listSessionTasks: vi.fn(),
  listTaskRunPreviews: vi.fn(),
  retryTaskRun: vi.fn(),
  retryTaskRunWithFallback: vi.fn(),
  sessionEventsUrl: vi.fn(),
  startTaskRunPreview: vi.fn(),
  stopPreview: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ replace: navigationMocks.replace }),
  useSearchParams: () => new URLSearchParams("session=session-1"),
}))

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  approveTaskRun: apiMocks.approveTaskRun,
  createPreviewDeployment: apiMocks.createPreviewDeployment,
  createSessionMessage: apiMocks.createSessionMessage,
  createTaskRun: apiMocks.createTaskRun,
  createWorkspaceSession: apiMocks.createWorkspaceSession,
  denyTaskRun: apiMocks.denyTaskRun,
  forceCodexFailure: apiMocks.forceCodexFailure,
  getSessionLedger: apiMocks.getSessionLedger,
  interruptTaskRun: apiMocks.interruptTaskRun,
  listSessionMessages: apiMocks.listSessionMessages,
  listSessionTasks: apiMocks.listSessionTasks,
  listTaskRunPreviews: apiMocks.listTaskRunPreviews,
  retryTaskRun: apiMocks.retryTaskRun,
  retryTaskRunWithFallback: apiMocks.retryTaskRunWithFallback,
  sessionEventsUrl: apiMocks.sessionEventsUrl,
  startTaskRunPreview: apiMocks.startTaskRunPreview,
  stopPreview: apiMocks.stopPreview,
}))

const workspace = {
  createdAt: "2026-05-16T00:00:00Z",
  defaultBranch: "main",
  id: "workspace-1",
  name: "AgentHub Demo",
  repoUrl: "local://apps/demo",
  rootPath: "apps/demo",
}

const initialSessions = [
  {
    boundBranch: "main",
    createdAt: "2026-05-16T00:00:00Z",
    id: "session-1",
    lastMessageAt: "2026-05-16T00:00:00Z",
    sessionType: "demo",
    status: "active",
    title: "Session 1",
    updatedAt: "2026-05-16T00:00:00Z",
    workspaceId: "workspace-1",
    worktreePath: "/repo/.worktrees/session-1",
  },
]

const initialAgents = [
  {
    adapterType: "scripted_mock",
    avatarInitials: "MO",
    capabilityTags: ["planning", "task assignment", "coordination"],
    contactType: "agent",
    description: "Plans the local demo workflow.",
    displayName: "Manager / Orchestrator",
    id: "agent-orchestrator",
    role: "orchestrator",
    safeForReview: true,
    safeForWrite: false,
    status: "available",
  },
  {
    adapterType: "codex",
    avatarInitials: "FE",
    capabilityTags: ["Vite React", "UI changes", "diff artifacts"],
    contactType: "agent",
    description: "Executes bounded frontend changes.",
    displayName: "Frontend Agent",
    id: "agent-frontend",
    role: "frontend",
    safeForReview: false,
    safeForWrite: true,
    status: "available",
  },
  {
    adapterType: "claude_code",
    avatarInitials: "RV",
    capabilityTags: ["planned", "read-only", "non-blocking review"],
    contactType: "placeholder",
    description: "Future non-blocking review workflow.",
    displayName: "Review Agent",
    id: "virtual-review-agent",
    role: "review",
    safeForReview: true,
    safeForWrite: false,
    status: "planned",
  },
]

class MockEventSource {
  onerror: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  constructor(readonly url: string) {}

  close = vi.fn()
}

describe("WorkspaceShell", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal("EventSource", MockEventSource)
    apiMocks.sessionEventsUrl.mockReturnValue(
      "http://127.0.0.1:8000/sessions/session-1/events?after=0&stream=true",
    )
    apiMocks.getSessionLedger.mockResolvedValue(null)
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it("shows a backend sync warning instead of leaking rejected session fetches", async () => {
    apiMocks.listSessionMessages.mockRejectedValue(new TypeError("Failed to fetch"))
    apiMocks.listSessionTasks.mockRejectedValue(new TypeError("Failed to fetch"))

    render(
      <WorkspaceShell
        backendUrl="http://127.0.0.1:8000"
        initialAgents={initialAgents}
        initialSessions={initialSessions}
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain(
        "请确认 FastAPI 后端可访问：http://127.0.0.1:8000。",
      )
    })
  })

  it("renders built-in agent contacts and local IM visual modes", async () => {
    apiMocks.listSessionMessages.mockResolvedValue([])
    apiMocks.listSessionTasks.mockResolvedValue([])

    render(
      <WorkspaceShell
        backendUrl="http://127.0.0.1:8000"
        initialAgents={initialAgents}
        initialSessions={initialSessions}
        workspace={workspace}
      />,
    )

    expect(screen.getByText("Agent 联系人")).toBeTruthy()
    expect(screen.getByText("Direct chat")).toBeTruthy()
    expect(screen.getByText("Group workflow")).toBeTruthy()
    expect(screen.getByText("Manager / Orchestrator")).toBeTruthy()
    expect(screen.getByText("Frontend Agent")).toBeTruthy()
    expect(screen.getByText("Review Agent")).toBeTruthy()
    expect(screen.getByText("@frontend · codex")).toBeTruthy()
    expect(screen.getByText("@review · claude_code")).toBeTruthy()
    expect(screen.getByText("计划中")).toBeTruthy()
  })

  it("renders the workspace context ledger for the selected session", async () => {
    apiMocks.listSessionMessages.mockResolvedValue([])
    apiMocks.listSessionTasks.mockResolvedValue([])
    apiMocks.getSessionLedger.mockResolvedValue({
      activeAgents: ["orchestrator", "frontend"],
      currentGoal: "@orchestrator build a login page for the demo app",
      id: "ledger-1",
      lastSuccessfulAdapter: "scripted_mock",
      latestChangedFiles: ["apps/demo/src/App.tsx"],
      latestDeploymentId: "deployment-1",
      latestDeploymentProvider: "mock",
      latestDeploymentStatus: "ready",
      latestDiffArtifactId: "artifact-diff-1",
      latestPreviewHealth: "healthy",
      latestPreviewId: "preview-1",
      latestPreviewUrl: "http://127.0.0.1:4317",
      latestTaskId: "task-1",
      latestTaskRunId: "run-1",
      sessionId: "session-1",
      summaryMd: "Current goal: @orchestrator build a login page",
      updatedAt: "2026-05-21T00:00:00Z",
    })

    render(
      <WorkspaceShell
        backendUrl="http://127.0.0.1:8000"
        initialAgents={initialAgents}
        initialSessions={initialSessions}
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText("Workspace Context")).toBeTruthy()
      expect(
        screen.getByText("@orchestrator build a login page for the demo app"),
      ).toBeTruthy()
      expect(screen.getByText("Mock deploy ready")).toBeTruthy()
      expect(screen.getByText("scripted_mock")).toBeTruthy()
      expect(screen.getByText("apps/demo/src/App.tsx")).toBeTruthy()
    })
  })
})
