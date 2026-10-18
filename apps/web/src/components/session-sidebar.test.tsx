import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { SessionSidebar } from "./session-sidebar"
import type { Workspace } from "@/lib/api"

afterEach(cleanup)

const workspace: Workspace = {
  id: "workspace-1",
  name: "AgentHub Demo",
  repoUrl: "local://apps/demo",
  rootPath: "apps/demo",
  defaultBranch: "main",
  createdAt: "2026-10-18T00:00:00Z",
}

function sidebar(name: string) {
  return render(<SessionSidebar agents={[]} isPending={false}
    onCreateSession={vi.fn()} onSelectSession={vi.fn()} selectedSessionId={null}
    sessions={[]} taskCount={0} workspace={{ ...workspace, name }} />)
}

describe("workspace display name", () => {
  it("shows AgentHub for a database with the legacy default workspace name", () => {
    sidebar("AgentHub Demo")
    expect(screen.getByRole("heading", { name: "AgentHub" })).toBeTruthy()
    expect(screen.getByText("本地工作区 · AgentHub")).toBeTruthy()
    expect(screen.queryByText(/AgentHub Demo/)).toBeNull()
    expect(workspace.name).toBe("AgentHub Demo")
  })

  it.each(["AgentHub", "我的研发工作区"])("preserves the workspace name %s", (name) => {
    sidebar(name)
    expect(screen.getByRole("heading", { name })).toBeTruthy()
    expect(screen.getByText(`本地工作区 · ${name}`)).toBeTruthy()
  })
})
