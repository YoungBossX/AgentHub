import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import Home from "./page"

vi.mock("@/components/health-card", () => ({
  HealthCard: () => <aside data-testid="health-card">Backend health</aside>,
}))

vi.mock("@/components/workspace-shell", () => ({
  WorkspaceShell: () => <section data-testid="workspace-shell">Workspace shell</section>,
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
  listWorkspaceSessions: vi.fn(async () => []),
}))

afterEach(() => cleanup())

describe("Home", () => {
  it("lets the workspace shell own the full content width for its preview panel", async () => {
    render(await Home())

    const workspaceShell = screen.getByTestId("workspace-shell")
    const contentGrid = workspaceShell.parentElement

    expect(contentGrid?.className).toBe("grid gap-4")
    expect(contentGrid?.className).not.toContain("md:grid-cols")
    expect(screen.getByTestId("health-card")).toBeTruthy()
  })
})
