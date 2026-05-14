import { render, screen } from "@testing-library/react"
import { createElement } from "react"
import { describe, expect, it } from "vitest"

import { TaskCardList } from "./task-card-list"
import type { SessionTask } from "@/lib/api"

const baseTask: SessionTask = {
  id: "task-1",
  sessionId: "session-1",
  createdByMessageId: "message-1",
  title: "Build the Vite React login page",
  intentType: "frontend_change",
  status: "pending",
  priority: 1,
  planJson: { target: "login_page" },
  dependsOnTaskIds: ["task-0"],
  assignedAgentId: "agent-frontend",
  assignedAgentRole: "frontend",
  createdAt: "2026-05-14T00:00:00Z",
  updatedAt: "2026-05-14T00:00:00Z",
}

describe("TaskCardList", () => {
  it("renders task titles, assigned agents, statuses, and dependencies", () => {
    render(createElement(TaskCardList, { tasks: [baseTask] }))

    expect(screen.getByText("Build the Vite React login page")).toBeTruthy()
    expect(screen.getByText("Step 1 · frontend")).toBeTruthy()
    expect(screen.getByText("pending")).toBeTruthy()
    expect(screen.getByText("Depends on task-0")).toBeTruthy()
  })
})
