import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AgentDirectorySettingsPageClient } from "./agent-directory-settings-page-client"
import type { AgentDirectory, Workspace } from "@/lib/api"

const apiMocks = vi.hoisted(() => ({
  createAgentProfileDraft: vi.fn(),
}))

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  createAgentProfileDraft: apiMocks.createAgentProfileDraft,
}))

const workspace: Workspace = {
  createdAt: "2026-05-16T00:00:00Z",
  defaultBranch: "main",
  id: "workspace-1",
  name: "AgentHub Demo",
  repoUrl: "local://apps/demo",
  rootPath: "apps/demo",
}

const directory: AgentDirectory = {
  entries: [
    {
      adapterType: "codex",
      authStatus: "unchecked",
      available: true,
      avatarInitials: "FE",
      capabilityTags: ["code_write", "preview"],
      compatibility: {
        compatible: true,
        mode: "frontend",
        reasons: [],
        requiredCapabilities: [],
        role: "frontend",
        targetId: null,
        warnings: [],
      },
      description: "Executes bounded frontend changes.",
      displayName: "Frontend Agent",
      entryType: "built_in",
      id: "agent-frontend",
      agentProfileId: "agent-frontend",
      providerId: "local-codex-cli",
      role: "frontend",
      runtimeSelectedForRoles: ["frontend"],
      safeForReview: false,
      safeForWrite: true,
      status: "available",
      supportedModes: ["frontend"],
      supportedTargets: ["demo-frontend", "external-frontend"],
    },
    {
      adapterType: "scripted_mock",
      authStatus: "not_required",
      available: false,
      avatarInitials: "DR",
      capabilityTags: ["code_review"],
      compatibility: {
        compatible: false,
        mode: "review",
        reasons: ["draft profile is disabled until validated"],
        requiredCapabilities: [],
        role: "review",
        targetId: null,
        warnings: [],
      },
      description: "Review-only draft.",
      displayName: "Draft Reviewer",
      entryType: "draft",
      id: "draft-reviewer",
      agentProfileId: "draft-reviewer",
      providerId: "local-scripted-mock",
      role: "review",
      runtimeSelectedForRoles: [],
      safeForReview: true,
      safeForWrite: false,
      status: "draft_only",
      supportedModes: ["review", "read_only"],
      supportedTargets: ["demo-frontend"],
    },
  ],
  workspaceId: "workspace-1",
}

describe("AgentDirectorySettingsPageClient", () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("renders provider, capability, target, safety, status, and compatibility metadata", () => {
    render(
      <AgentDirectorySettingsPageClient directory={directory} workspace={workspace} />,
    )

    expect(screen.getByText("Frontend Agent")).toBeTruthy()
    expect(screen.getAllByText("local-codex-cli").length).toBeGreaterThan(0)
    expect(screen.getAllByText("code_write").length).toBeGreaterThan(0)
    expect(screen.getAllByText("external-frontend").length).toBeGreaterThan(0)
    expect(screen.getByText("已选：frontend")).toBeTruthy()
    expect(screen.getAllByText("可用").length).toBeGreaterThan(0)
    expect(screen.getByText("可写")).toBeTruthy()
    expect(screen.getByText("Draft Reviewer")).toBeTruthy()
    expect(screen.getAllByText("草稿").length).toBeGreaterThan(0)
    expect(screen.getByText("不兼容")).toBeTruthy()
    expect(screen.getByText("draft profile is disabled until validated")).toBeTruthy()
  })

  it("filters directory entries by role, provider, capability, target, and status", () => {
    render(
      <AgentDirectorySettingsPageClient directory={directory} workspace={workspace} />,
    )

    fireEvent.change(screen.getByLabelText("角色筛选"), {
      target: { value: "frontend" },
    })
    expect(screen.getByText("Frontend Agent")).toBeTruthy()
    expect(screen.queryByText("Draft Reviewer")).toBeNull()

    fireEvent.change(screen.getByLabelText("角色筛选"), { target: { value: "all" } })
    fireEvent.change(screen.getByLabelText("状态筛选"), {
      target: { value: "draft_only" },
    })
    expect(screen.queryByText("Frontend Agent")).toBeNull()
    expect(screen.getByText("Draft Reviewer")).toBeTruthy()

    fireEvent.change(screen.getByLabelText("状态筛选"), { target: { value: "all" } })
    fireEvent.change(screen.getByLabelText("能力筛选"), {
      target: { value: "preview" },
    })
    expect(screen.getByText("Frontend Agent")).toBeTruthy()
    expect(screen.queryByText("Draft Reviewer")).toBeNull()

    fireEvent.change(screen.getByLabelText("能力筛选"), { target: { value: "all" } })
    fireEvent.change(screen.getByLabelText("目标筛选"), {
      target: { value: "demo-frontend" },
    })
    expect(screen.getByText("Frontend Agent")).toBeTruthy()
    expect(screen.getByText("Draft Reviewer")).toBeTruthy()

    fireEvent.change(screen.getByLabelText("Provider 筛选"), {
      target: { value: "local-scripted-mock" },
    })
    expect(screen.queryByText("Frontend Agent")).toBeNull()
    expect(screen.getByText("Draft Reviewer")).toBeTruthy()
  })

  it("saves a safe draft and shows it as draft-only without execution controls", async () => {
    apiMocks.createAgentProfileDraft.mockResolvedValue({
      adapterType: "scripted_mock",
      avatarInitials: "UR",
      capabilityTags: ["code_review", "diff_analysis"],
      description: "Review UI evidence.",
      displayName: "UI Reviewer",
      id: "draft-ui-reviewer",
      providerId: "local-scripted-mock",
      role: "ui_review",
      safeForReview: true,
      safeForWrite: false,
      status: "draft_only",
      supportedModes: ["review", "read_only"],
      supportedRoles: ["ui_review"],
      supportedTargets: ["demo-frontend"],
    })
    render(
      <AgentDirectorySettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        directory={directory}
        workspace={workspace}
      />,
    )

    fireEvent.change(screen.getByLabelText("草稿名称"), {
      target: { value: "UI Reviewer" },
    })
    fireEvent.change(screen.getByLabelText("草稿角色"), {
      target: { value: "ui_review" },
    })
    fireEvent.change(screen.getByLabelText("草稿描述"), {
      target: { value: "Review UI evidence." },
    })
    fireEvent.click(screen.getByRole("button", { name: "保存草稿" }))

    expect(apiMocks.createAgentProfileDraft).toHaveBeenCalledWith(
      "http://127.0.0.1:8000",
      "workspace-1",
      {
        adapterType: "scripted_mock",
        capabilityTags: ["code_review", "diff_analysis"],
        description: "Review UI evidence.",
        displayName: "UI Reviewer",
        providerId: "local-scripted-mock",
        role: "ui_review",
        safeForReview: true,
        safeForWrite: false,
        supportedModes: ["review", "read_only"],
        supportedTargets: ["demo-frontend"],
      },
    )
    expect(await screen.findByText("UI Reviewer")).toBeTruthy()
    expect(screen.getAllByText("草稿").length).toBeGreaterThan(0)
    expect(screen.queryByLabelText("Shell commands")).toBeNull()
    expect(screen.queryByLabelText("Tool permissions")).toBeNull()
  })

  it("cancels draft edits without saving", () => {
    render(
      <AgentDirectorySettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        directory={directory}
        workspace={workspace}
      />,
    )

    fireEvent.change(screen.getByLabelText("草稿名称"), {
      target: { value: "Temporary Reviewer" },
    })
    fireEvent.click(screen.getByRole("button", { name: "取消" }))

    expect((screen.getByLabelText("草稿名称") as HTMLInputElement).value).toBe("")
    expect(apiMocks.createAgentProfileDraft).not.toHaveBeenCalled()
  })

  it("shows draft validation errors without creating unsafe controls", async () => {
    apiMocks.createAgentProfileDraft.mockRejectedValue(new Error("Draft agents cannot define shell commands."))
    render(
      <AgentDirectorySettingsPageClient
        backendUrl="http://127.0.0.1:8000"
        directory={directory}
        workspace={workspace}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: "保存草稿" }))
    expect(await screen.findByText("请填写草稿名称和角色。")).toBeTruthy()

    fireEvent.change(screen.getByLabelText("草稿名称"), {
      target: { value: "Unsafe Reviewer" },
    })
    fireEvent.change(screen.getByLabelText("草稿角色"), {
      target: { value: "unsafe_review" },
    })
    fireEvent.click(screen.getByRole("button", { name: "保存草稿" }))

    expect(
      await screen.findByText("Draft agents cannot define shell commands."),
    ).toBeTruthy()
    expect(screen.queryByLabelText("Shell commands")).toBeNull()
    expect(screen.queryByLabelText("Tool permissions")).toBeNull()
  })
})
