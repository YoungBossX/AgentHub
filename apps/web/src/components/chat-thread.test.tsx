import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { createElement } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatThread } from "./chat-thread"
import type { ChatMessage, WorkspaceSession } from "@/lib/api"

afterEach(() => cleanup())

const session: WorkspaceSession = {
  boundBranch: "main",
  createdAt: "2026-05-16T00:00:00Z",
  id: "session-1",
  lastMessageAt: "2026-05-16T00:00:00Z",
  sessionType: "demo",
  status: "active",
  title: "Session 1",
  updatedAt: "2026-05-16T00:00:00Z",
  workspaceId: "workspace-1",
  worktreePath: "/repo/.worktrees/session-1",
}

const message: ChatMessage = {
  contentMd: "Build a dashboard",
  createdAt: "2026-05-16T00:00:00Z",
  id: "message-1",
  messageKind: "chat",
  parentMessageId: null,
  senderId: null,
  senderType: "user",
  sessionId: "session-1",
  streamState: "complete",
}

describe("ChatThread", () => {
  it("supports copy and quote message actions", () => {
    const writeText = vi.fn()
    const onQuoteMessage = vi.fn()
    vi.stubGlobal("navigator", { clipboard: { writeText } })

    render(
      createElement(ChatThread, {
        messages: [message],
        onQuoteMessage,
        selectedSession: session,
        taskCount: 0,
      }),
    )

    fireEvent.click(screen.getByRole("button", { name: "Copy message" }))
    fireEvent.click(screen.getByRole("button", { name: "Quote as context" }))

    expect(writeText).toHaveBeenCalledWith("Build a dashboard")
    expect(onQuoteMessage).toHaveBeenCalledWith(message)
  })
})
