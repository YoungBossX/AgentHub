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
  getSessionArtifactWorkbench: vi.fn(),
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
  getSessionArtifactWorkbench: apiMocks.getSessionArtifactWorkbench,
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
    activeBackendTargetId: "demo-backend",
    activeFrontendTargetId: "demo-frontend",
    boundBranch: "main",
    createdAt: "2026-05-16T00:00:00Z",
    id: "session-1",
    lastMessageAt: "2026-05-16T00:00:00Z",
    memorySnapshotId: "memory-snapshot-123456789",
    sessionType: "demo",
    status: "active",
    title: "Session 1",
    updatedAt: "2026-05-16T00:00:00Z",
    workspaceId: "workspace-1",
    worktreePath: "/repo/.worktrees/session-1",
  },
]

const searchableSessions = [
  initialSessions[0],
  {
    activeBackendTargetId: null,
    activeFrontendTargetId: "external-library-app",
    boundBranch: "main",
    createdAt: "2026-05-16T01:00:00Z",
    id: "session-2",
    lastMessageAt: "2026-05-17T00:00:00Z",
    memorySnapshotId: null,
    sessionType: "demo",
    status: "active",
    title: "Library app rehearsal",
    updatedAt: "2026-05-17T00:00:00Z",
    workspaceId: "workspace-1",
    worktreePath: "/repo/.worktrees/session-2",
  },
  {
    activeBackendTargetId: "external-backend-api",
    activeFrontendTargetId: null,
    boundBranch: "main",
    createdAt: "2026-05-16T02:00:00Z",
    id: "session-3",
    lastMessageAt: null,
    memorySnapshotId: null,
    sessionType: "demo",
    status: "active",
    title: "Backend API cleanup",
    updatedAt: "2026-05-16T02:00:00Z",
    workspaceId: "workspace-1",
    worktreePath: "/repo/.worktrees/session-3",
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
    apiMocks.getSessionArtifactWorkbench.mockResolvedValue({
      artifacts: [],
      sessionId: "session-1",
    })
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

  it("renders settings navigation links and keeps contacts off the chat sidebar", async () => {
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

    expect(screen.getByText("联系人设置").closest("a")?.getAttribute("href")).toBe(
      "/settings/contacts",
    )
    expect(screen.getByText("Agent 目录").closest("a")?.getAttribute("href")).toBe(
      "/settings/agents",
    )
    expect(screen.getByText("运行设置").closest("a")?.getAttribute("href")).toBe(
      "/settings/runtime",
    )
    expect(screen.getByText("记忆设置").closest("a")?.getAttribute("href")).toBe(
      "/settings/memory",
    )
    expect(screen.getByText("其他设置").closest("a")?.getAttribute("href")).toBe(
      "/settings/other",
    )
    expect(screen.getByText("新建会话")).toBeTruthy()
    expect(screen.queryByText("Agent 联系人")).toBeNull()
    expect(screen.queryByText("Direct chat")).toBeNull()
  })

  it("keeps detailed runtime settings out of the chat sidebar", async () => {
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
      expect(screen.getByText("最近会话")).toBeTruthy()
    })

    expect(screen.getByText("运行设置").closest("a")?.getAttribute("href")).toBe(
      "/settings/runtime",
    )
    expect(screen.queryByLabelText("规划 API")).toBeNull()
    expect(screen.queryByText("Save runtime config")).toBeNull()
    expect(apiMocks.getAgentRuntimeConfig).not.toHaveBeenCalled()
    expect(apiMocks.updateAgentRuntimeConfig).not.toHaveBeenCalled()
  })

  it("shows direct and group conversation modes without creating tasks", async () => {
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
      expect(screen.getByText("对话模式")).toBeTruthy()
      expect(screen.getByText("群聊")).toBeTruthy()
    })

    fireEvent.click(screen.getByRole("button", { name: "单聊" }))

    expect(screen.getByText("单聊聚焦当前对话，不改变后端路由。")).toBeTruthy()
    expect(apiMocks.createSessionMessage).not.toHaveBeenCalled()
    expect(apiMocks.createTaskRun).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "群聊" }))

    expect(
      screen.getByText("群聊显示 Orchestrator 与角色 Agent 协作，不改变调度规则。"),
    ).toBeTruthy()
    expect(apiMocks.createTaskRun).not.toHaveBeenCalled()
  })

  it("stages quoted messages as composer context and clears them", async () => {
    const existingMessage = {
      contentMd: "请实现一个图书管理系统",
      createdAt: "2026-06-07T00:00:00Z",
      id: "message-existing",
      messageKind: "chat",
      parentMessageId: null,
      senderId: null,
      senderType: "user",
      sessionId: "session-1",
      streamState: "complete",
    }
    apiMocks.listSessionMessages.mockResolvedValue([existingMessage])
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
      expect(screen.getByText("请实现一个图书管理系统")).toBeTruthy()
    })

    fireEvent.click(screen.getByRole("button", { name: "Quote as context" }))

    expect(screen.getByText("待发送上下文")).toBeTruthy()
    expect(screen.getByText("引用消息 · 用户")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "清除上下文" }))

    expect(screen.queryByText("待发送上下文")).toBeNull()
    expect(apiMocks.createSessionMessage).not.toHaveBeenCalled()
  })

  it("filters sessions from the sidebar without clearing the selected session", async () => {
    apiMocks.listSessionMessages.mockResolvedValue([])
    apiMocks.listSessionTasks.mockResolvedValue([])

    render(
      <WorkspaceShell
        backendUrl="http://127.0.0.1:8000"
        initialAgents={initialAgents}
        initialSessions={searchableSessions}
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getAllByText("Session 1").length).toBeGreaterThan(0)
      expect(screen.getByText("Library app rehearsal")).toBeTruthy()
      expect(screen.getByText("Backend API cleanup")).toBeTruthy()
    })

    fireEvent.change(screen.getByLabelText("搜索会话"), {
      target: { value: "library" },
    })

    expect(screen.getByText("Library app rehearsal")).toBeTruthy()
    expect(screen.queryByText("Backend API cleanup")).toBeNull()
    expect(screen.getByText("当前会话")).toBeTruthy()
    expect(screen.getByRole("heading", { name: "Session 1" })).toBeTruthy()
    expect(apiMocks.createTaskRun).not.toHaveBeenCalled()
  })

  it("shows an empty search state while preserving session focus", async () => {
    apiMocks.listSessionMessages.mockResolvedValue([])
    apiMocks.listSessionTasks.mockResolvedValue([])

    render(
      <WorkspaceShell
        backendUrl="http://127.0.0.1:8000"
        initialAgents={initialAgents}
        initialSessions={searchableSessions}
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByLabelText("搜索会话")).toBeTruthy()
    })

    fireEvent.change(screen.getByLabelText("搜索会话"), {
      target: { value: "no such session" },
    })

    expect(screen.getByText("没有匹配的会话。")).toBeTruthy()
    expect(screen.getByText("当前聚焦 0 个任务")).toBeTruthy()
    expect(screen.getByRole("heading", { name: "Session 1" })).toBeTruthy()
    expect(apiMocks.createSessionMessage).not.toHaveBeenCalled()
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
      expect(screen.getByText("Deploy ready")).toBeTruthy()
      expect(screen.getByText("scripted_mock")).toBeTruthy()
      expect(screen.getByText("apps/demo/src/App.tsx")).toBeTruthy()
      expect(screen.getByText("demo-frontend")).toBeTruthy()
      expect(screen.getByText("demo-backend")).toBeTruthy()
      expect(screen.getByText("memory-s")).toBeTruthy()
      expect(screen.getByText("mock")).toBeTruthy()
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
        "我还不能安全地把这条消息直接变成可执行任务。如果要写入桌面或其他本地目录，请先把对应目录注册为外部工作区/目标；如果只是想改当前 demo，请提出一个限定在 demo app 内的前端/后端变更，或显式使用 @frontend / @backend 指派。",
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
          "我还不能安全地把这条消息直接变成可执行任务。如果要写入桌面或其他本地目录，请先把对应目录注册为外部工作区/目标；如果只是想改当前 demo，请提出一个限定在 demo app 内的前端/后端变更，或显式使用 @frontend / @backend 指派。",
        ),
      ).toBeTruthy()
    })
    expect(apiMocks.listSessionMessages).toHaveBeenLastCalledWith(
      "http://127.0.0.1:8000",
      "session-1",
    )
  })
})
