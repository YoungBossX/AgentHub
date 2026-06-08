import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { AgentDirectorySettingsPageClient } from "./agent-directory-settings-page-client"
import type { AgentDirectory, Workspace } from "@/lib/api"

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
})
