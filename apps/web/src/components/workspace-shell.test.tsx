import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
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
  createTaskRunReview: vi.fn(),
  createWorkspaceSession: vi.fn(),
  denyTaskRun: vi.fn(),
  forceCodexFailure: vi.fn(),
  getAgentRuntimeConfig: vi.fn(),
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
  updateAgentRuntimeConfig: vi.fn(),
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
  createTaskRunReview: apiMocks.createTaskRunReview,
  createWorkspaceSession: apiMocks.createWorkspaceSession,
  denyTaskRun: apiMocks.denyTaskRun,
  forceCodexFailure: apiMocks.forceCodexFailure,
  getAgentRuntimeConfig: apiMocks.getAgentRuntimeConfig,
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
  updateAgentRuntimeConfig: apiMocks.updateAgentRuntimeConfig,
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
    providerId: "local-scripted-mock",
    role: "orchestrator",
    safeForReview: true,
    safeForWrite: false,
    status: "available",
    supportedModes: ["read_only"],
    supportedTargets: ["demo-frontend", "demo-backend"],
  },
  {
    adapterType: "codex",
    avatarInitials: "FE",
    capabilityTags: ["Vite React", "UI changes", "diff artifacts"],
    contactType: "agent",
    description: "Executes bounded frontend changes.",
    displayName: "Frontend Agent",
    id: "agent-frontend",
    providerId: "local-codex-cli",
    role: "frontend",
    safeForReview: false,
    safeForWrite: true,
    status: "available",
    supportedModes: ["frontend"],
    supportedTargets: ["demo-frontend", "external-frontend"],
  },
  {
    adapterType: "claude_code",
    avatarInitials: "RV",
    capabilityTags: ["planned", "read-only", "non-blocking review"],
    contactType: "placeholder",
    description: "Future non-blocking review workflow.",
    displayName: "Review Agent",
    id: "virtual-review-agent",
    providerId: "local-claude-code-cli",
    role: "review",
    safeForReview: true,
    safeForWrite: false,
    status: "planned",
    supportedModes: ["review", "read_only"],
    supportedTargets: ["demo-frontend", "demo-backend"],
  },
]

const runtimeConfig = {
  availableProfiles: [
    {
      adapterType: "scripted_mock",
      avatarInitials: "MO",
      capabilityTags: ["diff_analysis", "code_review"],
      description: "Plans the local workflow.",
      displayName: "Manager / Orchestrator",
      id: "agent-orchestrator",
      providerId: "local-scripted-mock",
      role: "orchestrator",
      safeForReview: true,
      safeForWrite: false,
      status: "available",
      supportedModes: ["read_only"],
      supportedRoles: ["orchestrator", "manager"],
      supportedTargets: ["demo-frontend", "demo-backend"],
    },
    {
      adapterType: "codex",
      avatarInitials: "FE",
      capabilityTags: ["code_write", "preview"],
      description: "Executes bounded frontend changes.",
      displayName: "Frontend Agent",
      id: "agent-frontend",
      providerId: "local-codex-cli",
      role: "frontend",
      safeForReview: false,
      safeForWrite: true,
      status: "available",
      supportedModes: ["frontend"],
      supportedRoles: ["frontend"],
      supportedTargets: ["demo-frontend", "external-frontend"],
    },
    {
      adapterType: "codex",
      avatarInitials: "BE",
      capabilityTags: ["code_write", "test_run"],
      description: "Executes bounded backend changes.",
      displayName: "Backend Agent",
      id: "agent-backend",
      providerId: "local-codex-cli",
      role: "backend",
      safeForReview: false,
      safeForWrite: true,
      status: "available",
      supportedModes: ["backend"],
      supportedRoles: ["backend"],
      supportedTargets: ["demo-backend", "external-backend"],
    },
  ],
  availableProviders: [
    {
      adapterType: "claude_cli",
      authStatus: "unchecked",
      available: true,
      defaultForRoles: ["planner"],
      displayName: "Claude CLI Planner",
      providerId: "claude-cli-planner",
      supportedModes: ["read_only"],
    },
    {
      adapterType: "claude_code",
      authStatus: "unchecked",
      available: true,
      defaultForRoles: ["frontend", "backend"],
      displayName: "Claude Code CLI",
      providerId: "local-claude-code-cli",
      supportedModes: ["frontend", "backend", "review", "debug"],
    },
    {
      adapterType: "codex",
      authStatus: "unchecked",
      available: true,
      defaultForRoles: ["frontend", "backend"],
      displayName: "Codex CLI",
      providerId: "local-codex-cli",
      supportedModes: ["frontend", "backend", "debug"],
    },
  ],
  configSource: "default",
  roles: {
    backend: {
      adapterType: null,
      agentProfileId: null,
      enabled: false,
      fallbackPolicy: "environment_default",
      mode: "backend",
      providerId: null,
      role: "backend",
    },
    frontend: {
      adapterType: null,
      agentProfileId: null,
      enabled: false,
      fallbackPolicy: "environment_default",
      mode: "frontend",
      providerId: null,
      role: "frontend",
    },
    planner: {
      adapterType: null,
      agentProfileId: null,
      apiKeyEnv: "DEEPSEEK_API_KEY",
      availability: "missing_key",
      baseUrl: "https://api.deepseek.com",
      enabled: false,
      fallbackPolicy: "environment_default",
      mode: "read_only",
      model: "deepseek-chat",
      protocol: "openai_compatible_chat",
      providerId: null,
      providerPresetId: "deepseek_api",
      role: "planner",
      timeoutSeconds: null,
    },
    review: {
      adapterType: null,
      agentProfileId: null,
      enabled: false,
      fallbackPolicy: "environment_default",
      mode: "read_only",
      providerId: null,
      role: "review",
    },
  },
  validation: { errors: [], valid: true, warnings: [] },
  workspaceId: "workspace-1",
}

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
    apiMocks.getAgentRuntimeConfig.mockResolvedValue(runtimeConfig)
    apiMocks.updateAgentRuntimeConfig.mockResolvedValue({
      ...runtimeConfig,
      configSource: "workspace",
    })
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
    expect(screen.getByText("local-codex-cli")).toBeTruthy()
    expect(screen.getAllByText("demo-frontend").length).toBeGreaterThan(0)
    expect(screen.getByText("计划中")).toBeTruthy()
  })

  it("renders agent runtime settings for planner, frontend, and backend", async () => {
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

    await waitFor(() => {
      expect(screen.getByText("Agent Runtime Settings")).toBeTruthy()
      expect(screen.getByText("Planner Agent")).toBeTruthy()
      expect(screen.getAllByText("Frontend Agent").length).toBeGreaterThan(0)
      expect(screen.getByText("Backend Agent")).toBeTruthy()
      expect(screen.getByText("Source: default")).toBeTruthy()
      expect(screen.getByText("Claude CLI Planner · unchecked")).toBeTruthy()
      expect(screen.getByText("DeepSeek API")).toBeTruthy()
      expect(screen.getByText("MiMo API")).toBeTruthy()
      expect(screen.getByText("missing_key")).toBeTruthy()
      expect(screen.getAllByText("Claude Code CLI · unchecked").length).toBeGreaterThan(0)
      expect(screen.getAllByText("Codex CLI · unchecked").length).toBeGreaterThan(0)
      expect(screen.getByText("Save runtime config")).toBeTruthy()
    })
  })

  it("saves planner API preset runtime settings", async () => {
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

    await waitFor(() => {
      expect(screen.getByLabelText("Planner API")).toBeTruthy()
    })

    fireEvent.change(screen.getByLabelText("Planner API"), {
      target: { value: "mimo_api" },
    })
    fireEvent.click(screen.getByText("Save runtime config"))

    await waitFor(() => {
      expect(apiMocks.updateAgentRuntimeConfig).toHaveBeenCalled()
    })

    const [, , roles] = apiMocks.updateAgentRuntimeConfig.mock.calls[0]
    expect(roles.planner.providerPresetId).toBe("mimo_api")
    expect(roles.planner.protocol).toBe("openai_compatible_chat")
    expect(roles.planner.model).toBe("mimo-v2.5-pro")
    expect(roles.planner.baseUrl).toBe("https://api.xiaomimimo.com/v1")
    expect(roles.planner.apiKeyEnv).toBe("MIMO_API_KEY")
    expect(roles.frontend.providerPresetId).toBeUndefined()
    expect(roles.frontend.apiKeyEnv).toBeUndefined()
    expect(roles.backend.providerPresetId).toBeUndefined()
    expect(roles.backend.apiKeyEnv).toBeUndefined()
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

  it("refreshes messages after send so backend-created replies appear immediately", async () => {
    const createdMessage = {
      contentMd: "你好",
      createdAt: "2026-05-29T08:13:55Z",
      id: "message-user",
      messageKind: "chat",
      parentMessageId: null,
      senderId: null,
      senderType: "user",
      sessionId: "session-1",
      streamState: "complete",
    }
    const orchestratorReply = {
      contentMd:
        "I could not safely turn that into a demo-target task yet. Please ask for a bounded change inside the demo app, or explicitly mention @frontend for a frontend assignment.",
      createdAt: "2026-05-29T08:13:56Z",
      id: "message-orchestrator",
      messageKind: "chat",
      parentMessageId: "message-user",
      senderId: "agent-orchestrator",
      senderType: "orchestrator",
      sessionId: "session-1",
      streamState: "complete",
    }
    apiMocks.listSessionMessages
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([createdMessage, orchestratorReply])
    apiMocks.listSessionTasks.mockResolvedValue([])
    apiMocks.createSessionMessage.mockResolvedValue(createdMessage)

    render(
      <WorkspaceShell
        backendUrl="http://127.0.0.1:8000"
        initialAgents={initialAgents}
        initialSessions={initialSessions}
        workspace={workspace}
      />,
    )

    const input = screen.getByPlaceholderText("@orchestrator 为演示应用构建登录页")
    fireEvent.change(input, { target: { value: "你好" } })
    fireEvent.submit(input.closest("form")!)

    await waitFor(() => {
      expect(
        screen.getByText(
          "I could not safely turn that into a demo-target task yet. Please ask for a bounded change inside the demo app, or explicitly mention @frontend for a frontend assignment.",
        ),
      ).toBeTruthy()
    })
    expect(apiMocks.listSessionMessages).toHaveBeenLastCalledWith(
      "http://127.0.0.1:8000",
      "session-1",
    )
  })
})
