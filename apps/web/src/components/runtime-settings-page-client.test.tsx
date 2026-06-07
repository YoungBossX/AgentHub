import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { RuntimeSettingsPageClient } from "./runtime-settings-page-client"
import type { AgentRuntimeConfig, Workspace } from "@/lib/api"

const apiMocks = vi.hoisted(() => ({
  checkAgentRuntimeProvider: vi.fn(),
  createExternalProjectTarget: vi.fn(),
  getAgentRuntimeConfig: vi.fn(),
  getDemoWorkspace: vi.fn(),
  listExternalTargetFolders: vi.fn(),
  listWorkspaceSessions: vi.fn(),
  listWorkspaceTargets: vi.fn(),
  updateAgentRuntimeConfig: vi.fn(),
  updateSessionTargetSelection: vi.fn(),
}))

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  checkAgentRuntimeProvider: apiMocks.checkAgentRuntimeProvider,
  createExternalProjectTarget: apiMocks.createExternalProjectTarget,
  getAgentRuntimeConfig: apiMocks.getAgentRuntimeConfig,
  getDemoWorkspace: apiMocks.getDemoWorkspace,
  listExternalTargetFolders: apiMocks.listExternalTargetFolders,
  listWorkspaceSessions: apiMocks.listWorkspaceSessions,
  listWorkspaceTargets: apiMocks.listWorkspaceTargets,
  updateAgentRuntimeConfig: apiMocks.updateAgentRuntimeConfig,
  updateSessionTargetSelection: apiMocks.updateSessionTargetSelection,
}))

const workspace: Workspace = {
  createdAt: "2026-05-16T00:00:00Z",
  defaultBranch: "main",
  id: "workspace-1",
  name: "AgentHub Demo",
  repoUrl: "local://apps/demo",
  rootPath: "apps/demo",
}

const runtimeConfig: AgentRuntimeConfig = {
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
      providerPresetId: null,
      protocol: null,
      model: null,
      baseUrl: null,
      timeoutSeconds: null,
      apiKeyEnv: null,
      availability: null,
      role: "backend",
    },
    frontend: {
      adapterType: null,
      agentProfileId: null,
      enabled: false,
      fallbackPolicy: "environment_default",
      mode: "frontend",
      providerId: null,
      providerPresetId: null,
      protocol: null,
      model: null,
      baseUrl: null,
      timeoutSeconds: null,
      apiKeyEnv: null,
      availability: null,
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
      providerPresetId: null,
      protocol: null,
      model: null,
      baseUrl: null,
      timeoutSeconds: null,
      apiKeyEnv: null,
      availability: null,
      role: "review",
    },
  },
  validation: { errors: [], valid: true, warnings: [] },
  workspaceId: "workspace-1",
}

const workspaceSessions = [
  {
    activeBackendTargetId: "demo-backend",
    activeFrontendTargetId: "demo-frontend",
    boundBranch: "main",
    createdAt: "2026-05-16T00:00:00Z",
    id: "session-1",
    lastMessageAt: "2026-05-16T00:00:00Z",
    sessionType: "demo",
    status: "active",
    title: "Mini CRM",
    updatedAt: "2026-05-16T00:00:00Z",
    workspaceId: "workspace-1",
    worktreePath: "/repo/.worktrees/session-1",
  },
]

const workspaceTargets = [
  {
    allowedAgents: ["frontend", "qa", "review"],
    allowedPaths: ["apps/demo/src"],
    analysisStatus: "ready",
    baseUrl: null,
    buildCommand: "pnpm build",
    checkCommand: "pnpm check",
    deniedPaths: [".env", "node_modules"],
    deployProviderIds: ["local_static"],
    detectedFramework: "vite-react",
    devCommand: "pnpm demo:dev",
    name: "Demo Frontend",
    packageManager: "pnpm",
    previewCommand: "pnpm demo:dev",
    projectType: "vite-react",
    relatedTargetIds: ["demo-backend"],
    requiresApproval: false,
    requiresPlatformMode: false,
    root: "apps/demo",
    stagingOutputDir: "dist",
    stagingServeCommand: null,
    targetId: "demo-frontend",
    testCommand: null,
    type: "frontend",
  },
  {
    allowedAgents: ["backend", "qa", "review"],
    allowedPaths: ["apps/demo-api/app", "apps/demo-api/tests"],
    analysisStatus: "ready",
    baseUrl: "http://127.0.0.1:5174",
    buildCommand: null,
    checkCommand: "python -m compileall .",
    deniedPaths: [".env", "node_modules"],
    deployProviderIds: [],
    detectedFramework: "fastapi",
    devCommand: "pnpm demo:api:dev",
    name: "Demo Backend",
    packageManager: "pip",
    previewCommand: null,
    projectType: "fastapi",
    relatedTargetIds: ["demo-frontend"],
    requiresApproval: false,
    requiresPlatformMode: false,
    root: "apps/demo-api",
    stagingOutputDir: null,
    stagingServeCommand: null,
    targetId: "demo-backend",
    testCommand: "pnpm demo:api:test",
    type: "backend",
  },
]

describe("RuntimeSettingsPageClient", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    apiMocks.getDemoWorkspace.mockResolvedValue(workspace)
    apiMocks.getAgentRuntimeConfig.mockResolvedValue(runtimeConfig)
    apiMocks.listWorkspaceSessions.mockResolvedValue(workspaceSessions)
    apiMocks.listWorkspaceTargets.mockResolvedValue(workspaceTargets)
    apiMocks.listExternalTargetFolders.mockResolvedValue({
      children: [
        { name: "sample-app", path: "/Users/demo/Desktop/sample-app" },
      ],
      currentPath: "/Users/demo/Desktop",
      parentPath: "/Users/demo",
      starts: [
        { label: "桌面", path: "/Users/demo/Desktop" },
        { label: "文档", path: "/Users/demo/Documents" },
        { label: "工作区附近", path: "/repo" },
      ],
    })
    apiMocks.createExternalProjectTarget.mockResolvedValue({
      allowedPaths: ["*"],
      analysisStatus: "manual",
      buildCommand: "pnpm build",
      checkCommand: "pnpm check",
      createdAt: "2026-06-02T00:00:00Z",
      deniedPaths: [".env", "node_modules"],
      deployProviderIds: [],
      detectedFramework: "vite-react",
      devCommand: "pnpm dev",
      id: "external-target-1",
      name: "前端外部项目 sample-app",
      packageManager: "pnpm",
      previewCommand: "pnpm dev",
      projectType: "vite-react",
      rootPath: "/Users/demo/Desktop/sample-app",
      stagingOutputDir: null,
      stagingServeCommand: null,
      targetId: "external-frontend-sample-app",
      testCommand: "pnpm test",
      updatedAt: "2026-06-02T00:00:00Z",
      workspaceId: "workspace-1",
    })
    apiMocks.updateSessionTargetSelection.mockResolvedValue({
      ...workspaceSessions[0],
      activeFrontendTargetId: "demo-frontend",
      activeBackendTargetId: "demo-backend",
    })
    apiMocks.checkAgentRuntimeProvider.mockResolvedValue({
      role: "planner",
      providerId: "deepseek_api",
      adapterType: "openai_compatible_chat",
      authStatus: "configured",
      availability: "configured",
      available: true,
      message: "DeepSeek API 已配置密钥环境变量。",
    })
    apiMocks.updateAgentRuntimeConfig.mockResolvedValue({
      ...runtimeConfig,
      configSource: "workspace",
      roles: {
        ...runtimeConfig.roles,
        planner: {
          ...runtimeConfig.roles.planner,
          apiKeyEnv: "MIMO_API_KEY",
          baseUrl: "https://api.xiaomimimo.com/v1",
          model: "mimo-v2.5-pro",
          providerPresetId: "mimo_api",
        },
      },
    })
  })

  afterEach(() => cleanup())

  it("loads the demo workspace on the client when the route renders immediately", async () => {
    render(
      <RuntimeSettingsPageClient backendUrl="http://127.0.0.1:8000" />,
    )

    expect(screen.getByText("正在加载运行设置...")).toBeTruthy()

    await waitFor(() => {
      expect(apiMocks.getDemoWorkspace).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
      )
      expect(apiMocks.getAgentRuntimeConfig).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "workspace-1",
      )
      expect(apiMocks.listWorkspaceTargets).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "workspace-1",
      )
      expect(screen.getByText("工作区设置")).toBeTruthy()
      expect(screen.getByText("当前会话目标")).toBeTruthy()
      expect(screen.getByText("规划模型")).toBeTruthy()
    })
  })

  it("saves the selected session target mapping from workspace settings", async () => {
    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByLabelText("前端目标")).toBeTruthy()
    })

    fireEvent.click(screen.getByText("保存目标"))

    await waitFor(() => {
      expect(apiMocks.updateSessionTargetSelection).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "session-1",
        {
          backendTargetId: "demo-backend",
          frontendTargetId: "demo-frontend",
        },
      )
      expect(screen.getByText("会话目标已保存。")).toBeTruthy()
    })
  })

  it("registers an external project from workspace settings", async () => {
    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByLabelText("项目路径")).toBeTruthy()
    })

    fireEvent.change(screen.getByLabelText("项目路径"), {
      target: { value: "/Users/demo/Desktop/sample-app" },
    })
    fireEvent.click(screen.getByText("注册"))

    await waitFor(() => {
      expect(apiMocks.createExternalProjectTarget).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "workspace-1",
        expect.objectContaining({
          name: "前端外部项目 sample-app",
          projectType: "external-frontend",
          allowedPaths: ["*"],
          rootPath: "/Users/demo/Desktop/sample-app",
          targetId: "external-frontend-sample-app",
        }),
      )
      expect(screen.getByText("外部项目已注册：前端外部项目 sample-app")).toBeTruthy()
    })
  })

  it("selects a local folder and registers the selected folder scope", async () => {
    apiMocks.listExternalTargetFolders.mockImplementation(
      async (_backendUrl: string, _workspaceId: string, path?: string) => {
        if (path === "/Users/demo/Desktop/sample-app") {
          return {
            children: [],
            currentPath: "/Users/demo/Desktop/sample-app",
            parentPath: "/Users/demo/Desktop",
            starts: [
              { label: "桌面", path: "/Users/demo/Desktop" },
              { label: "文档", path: "/Users/demo/Documents" },
              { label: "工作区附近", path: "/repo" },
            ],
          }
        }

        return {
          children: [
            { name: "sample-app", path: "/Users/demo/Desktop/sample-app" },
          ],
          currentPath: "/Users/demo/Desktop",
          parentPath: "/Users/demo",
          starts: [
            { label: "桌面", path: "/Users/demo/Desktop" },
            { label: "文档", path: "/Users/demo/Documents" },
            { label: "工作区附近", path: "/repo" },
          ],
        }
      },
    )

    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText("选择文件夹")).toBeTruthy()
    })

    fireEvent.click(screen.getByText("选择文件夹"))

    await waitFor(() => {
      expect(apiMocks.listExternalTargetFolders).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "workspace-1",
        undefined,
      )
      expect(screen.getByText("sample-app")).toBeTruthy()
    })

    fireEvent.click(screen.getByText("sample-app"))

    await waitFor(() => {
      expect(apiMocks.listExternalTargetFolders).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "workspace-1",
        "/Users/demo/Desktop/sample-app",
      )
    })

    fireEvent.click(screen.getByText("选择当前文件夹"))
    fireEvent.click(screen.getByText("注册"))

    await waitFor(() => {
      expect(apiMocks.createExternalProjectTarget).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "workspace-1",
        expect.objectContaining({
          allowedPaths: ["*"],
          projectType: "external-frontend",
          rootPath: "/Users/demo/Desktop/sample-app",
        }),
      )
    })
  })

  it("registers a selected folder as a backend target", async () => {
    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByLabelText("项目路径")).toBeTruthy()
    })

    fireEvent.change(screen.getByLabelText("目标类型"), {
      target: { value: "backend" },
    })
    fireEvent.change(screen.getByLabelText("项目路径"), {
      target: { value: "/Users/demo/Desktop/sample-api" },
    })
    fireEvent.click(screen.getByText("注册"))

    await waitFor(() => {
      expect(apiMocks.createExternalProjectTarget).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "workspace-1",
        expect.objectContaining({
          name: "后端外部项目 sample-api",
          allowedPaths: ["*"],
          projectType: "external-backend",
          rootPath: "/Users/demo/Desktop/sample-api",
          targetId: "external-backend-sample-api",
        }),
      )
    })
  })

  it("keeps edits as draft until Save is clicked", async () => {
    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText("规划模型")).toBeTruthy()
    })

    fireEvent.change(screen.getByLabelText("规划 API"), {
      target: { value: "mimo_api" },
    })

    expect(screen.getByText("有未保存更改，点击保存后才会生效。")).toBeTruthy()
    expect(apiMocks.updateAgentRuntimeConfig).not.toHaveBeenCalled()
  })

  it("cancels draft changes by restoring persisted config", async () => {
    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByLabelText("规划 API")).toBeTruthy()
    })

    const plannerApi = screen.getByLabelText("规划 API") as HTMLSelectElement
    fireEvent.change(plannerApi, { target: { value: "mimo_api" } })
    fireEvent.click(screen.getByText("取消"))

    expect(screen.getByText("已取消未保存更改。")).toBeTruthy()
    expect(plannerApi.value).toBe("deepseek_api")
    expect(apiMocks.updateAgentRuntimeConfig).not.toHaveBeenCalled()
  })

  it("saves draft settings through the existing runtime config API", async () => {
    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByLabelText("规划 API")).toBeTruthy()
    })

    fireEvent.change(screen.getByLabelText("规划 API"), {
      target: { value: "mimo_api" },
    })
    fireEvent.click(screen.getByText("保存"))

    await waitFor(() => {
      expect(apiMocks.updateAgentRuntimeConfig).toHaveBeenCalled()
    })

    const [, workspaceId, roles] = apiMocks.updateAgentRuntimeConfig.mock.calls[0]
    expect(workspaceId).toBe("workspace-1")
    expect(roles.planner.providerPresetId).toBe("mimo_api")
    expect(roles.planner.protocol).toBe("openai_compatible_chat")
    expect(roles.planner.model).toBe("mimo-v2.5-pro")
    expect(roles.planner.baseUrl).toBe("https://api.xiaomimimo.com/v1")
    expect(roles.planner.apiKeyEnv).toBe("MIMO_API_KEY")

    await waitFor(() => {
      expect(screen.getByText("运行设置已保存。")).toBeTruthy()
    })
  })

  it("presents provider status with user-facing labels instead of raw internal values", async () => {
    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText("规划模型")).toBeTruthy()
    })

    expect(screen.getAllByText(/未检测/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/缺少密钥环境变量/).length).toBeGreaterThan(0)
    expect(screen.getByText(/缺少环境变量 DEEPSEEK_API_KEY/)).toBeTruthy()
    expect(screen.queryByText("missing_key")).toBeNull()
    expect(screen.queryByText("Claude CLI Planner · unchecked")).toBeNull()
  })

  it("checks a runtime provider and updates the visible status", async () => {
    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByLabelText("规划 API")).toBeTruthy()
    })

    fireEvent.click(screen.getAllByRole("button", { name: "检测" })[0])

    await waitFor(() => {
      expect(apiMocks.checkAgentRuntimeProvider).toHaveBeenCalledWith(
        "http://127.0.0.1:8000",
        "workspace-1",
        "planner",
        expect.objectContaining({
          providerPresetId: "deepseek_api",
          apiKeyEnv: "DEEPSEEK_API_KEY",
        }),
      )
      expect(screen.getByText("DeepSeek API 已配置密钥环境变量。")).toBeTruthy()
      expect(screen.getAllByText("已配置").length).toBeGreaterThan(0)
    })
  })
})
