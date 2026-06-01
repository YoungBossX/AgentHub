import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { RuntimeSettingsPageClient } from "./runtime-settings-page-client"
import type { AgentRuntimeConfig, Workspace } from "@/lib/api"

const apiMocks = vi.hoisted(() => ({
  getAgentRuntimeConfig: vi.fn(),
  updateAgentRuntimeConfig: vi.fn(),
}))

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAgentRuntimeConfig: apiMocks.getAgentRuntimeConfig,
  updateAgentRuntimeConfig: apiMocks.updateAgentRuntimeConfig,
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

describe("RuntimeSettingsPageClient", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    apiMocks.getAgentRuntimeConfig.mockResolvedValue(runtimeConfig)
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

  it("keeps edits as draft until Save is clicked", async () => {
    render(
      <RuntimeSettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        workspace={workspace}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText("Planner LLM")).toBeTruthy()
    })

    fireEvent.change(screen.getByLabelText("Planner API"), {
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
      expect(screen.getByLabelText("Planner API")).toBeTruthy()
    })

    const plannerApi = screen.getByLabelText("Planner API") as HTMLSelectElement
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
      expect(screen.getByLabelText("Planner API")).toBeTruthy()
    })

    fireEvent.change(screen.getByLabelText("Planner API"), {
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
      expect(screen.getByText("Planner LLM")).toBeTruthy()
    })

    expect(screen.getAllByText(/未检测/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/缺少密钥环境变量/).length).toBeGreaterThan(0)
    expect(
      screen.getByText(/API Key 只从后端进程环境变量读取/),
    ).toBeTruthy()
    expect(screen.getByText(/缺少环境变量 DEEPSEEK_API_KEY/)).toBeTruthy()
    expect(screen.queryByText("missing_key")).toBeNull()
    expect(screen.queryByText("Claude CLI Planner · unchecked")).toBeNull()
  })
})
