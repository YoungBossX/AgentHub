import { cleanup, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import Home from "./page"

vi.mock("@/components/health-card", () => ({
  HealthCard: () => <aside data-testid="health-card">Backend health</aside>,
}))

vi.mock("@/components/workspace-shell", () => ({
  WorkspaceShell: ({ healthSlot }: { healthSlot?: ReactNode }) => (
    <section data-testid="workspace-shell">
      Workspace shell
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
  })
})
