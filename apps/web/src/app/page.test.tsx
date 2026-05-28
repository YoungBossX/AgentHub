import { cleanup, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import Home from "./page"
import type { AgentContact } from "@/lib/api"

vi.mock("@/components/health-card", () => ({
  HealthCard: () => <aside data-testid="health-card">Backend health</aside>,
}))

vi.mock("@/components/workspace-shell", () => ({
  WorkspaceShell: ({
    healthSlot,
    initialAgents,
  }: {
    healthSlot?: ReactNode
    initialAgents: AgentContact[]
  }) => (
    <section data-testid="workspace-shell">
      Workspace shell
      <span data-testid="agent-count">{initialAgents.length}</span>
      {healthSlot ? <div data-testid="health-slot">{healthSlot}</div> : null}
    </section>
  ),
}))

vi.mock("@/lib/api", () => ({
  getBackendHealth: vi.fn(async () => ({
    database: "ready",
    service: "agenthub-api",
    status: "ok",
  })),
  getDemoWorkspace: vi.fn(async () => ({
    createdAt: "2026-05-16T00:00:00Z",
    defaultBranch: "main",
    id: "workspace-1",
    name: "AgentHub Demo",
    repoUrl: "local://apps/demo",
    rootPath: "apps/demo",
  })),
  listWorkspaceAgents: vi.fn(async () => [
    {
      adapterType: "scripted_mock",
      avatarInitials: "MO",
      capabilityTags: ["planning"],
      contactType: "agent",
      description: "Plans the workflow.",
      displayName: "Manager / Orchestrator",
      id: "agent-orchestrator",
      providerId: "local-scripted-mock",
      role: "orchestrator",
      safeForReview: true,
      safeForWrite: false,
      status: "available",
      supportedModes: ["read_only"],
      supportedTargets: ["demo-frontend"],
    },
  ]),
  listWorkspaceSessions: vi.fn(async () => []),
}))

afterEach(() => cleanup())

describe("Home", () => {
  it("lets the workspace shell own the command-center page structure", async () => {
    render(await Home())

    const workspaceShell = screen.getByTestId("workspace-shell")

    expect(workspaceShell.parentElement?.className).toContain("h-screen")
    expect(workspaceShell.parentElement?.className).toContain("overflow-hidden")
    expect(workspaceShell.parentElement?.className).not.toContain("max-w-[1440px]")
    expect(screen.getByTestId("health-card")).toBeTruthy()
    expect(screen.getByTestId("health-slot")).toBeTruthy()
    expect(screen.getByTestId("agent-count").textContent).toBe("1")
  })
})
