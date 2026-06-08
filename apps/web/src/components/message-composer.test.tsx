import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  buildComposerMessageContext,
  contextItemFromArtifact,
  contextItemFromMessage,
  MessageComposer,
} from "./message-composer"
import type { ArtifactPanelItem } from "@/components/preview-card"
import type { ChatMessage } from "@/lib/api"

afterEach(() => cleanup())

const contextMessage: ChatMessage = {
  contentMd: "请基于这个登录需求继续完善。",
  createdAt: "2026-06-07T00:00:00Z",
  id: "message-1",
  messageKind: "chat",
  parentMessageId: null,
  senderId: null,
  senderType: "user",
  sessionId: "session-1",
  streamState: "complete",
}

const contextArtifact: ArtifactPanelItem = {
  artifact: {
    artifactId: "artifact-diff-1",
    artifactType: "diff",
    baseRef: "base",
    changedFiles: ["src/App.tsx"],
    headRef: "head",
    id: "diff-1",
    patchText: "",
    stats: {
      additions: 3,
      deletions: 1,
      files: [{ additions: 3, deletions: 1, path: "src/App.tsx" }],
      filesChanged: 1,
    },
    status: "ready",
    taskRunId: "run-123456789",
    title: "Git Diff",
  },
  id: "diff:diff-1",
  kind: "diff",
  taskRunId: "run-123456789",
  taskTitle: "实现登录页",
}

describe("MessageComposer", () => {
  it("shows quoted message context before send", () => {
    const onClearContext = vi.fn()

    render(
      <MessageComposer
        contextItems={[contextItemFromMessage(contextMessage)]}
        draft="继续"
        isPending={false}
        onClearContext={onClearContext}
        onDraftChange={vi.fn()}
        onMoveContextItem={vi.fn()}
        onRemoveContextItem={vi.fn()}
        onSubmit={vi.fn()}
      />,
    )

    expect(screen.getByText("待发送上下文")).toBeTruthy()
    expect(screen.getByText("引用消息 · 用户")).toBeTruthy()
    expect(screen.getByText("请基于这个登录需求继续完善。")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "清除上下文" }))

    expect(onClearContext).toHaveBeenCalled()
  })

  it("shows artifact context before send", () => {
    render(
      <MessageComposer
        contextItems={[contextItemFromArtifact(contextArtifact)]}
        draft="检查这个 diff"
        isPending={false}
        onClearContext={vi.fn()}
        onDraftChange={vi.fn()}
        onMoveContextItem={vi.fn()}
        onRemoveContextItem={vi.fn()}
        onSubmit={vi.fn()}
      />,
    )

    expect(screen.getByText("待发送上下文")).toBeTruthy()
    expect(screen.getByText(/Diff 产物/)).toBeTruthy()
    expect(screen.getAllByText(/实现登录页/).length).toBeGreaterThan(0)
  })

  it("lets users remove and reorder multiple context items", () => {
    const onMoveContextItem = vi.fn()
    const onRemoveContextItem = vi.fn()

    render(
      <MessageComposer
        contextItems={[
          contextItemFromMessage(contextMessage),
          contextItemFromArtifact(contextArtifact),
        ]}
        draft="继续"
        isPending={false}
        onClearContext={vi.fn()}
        onDraftChange={vi.fn()}
        onMoveContextItem={onMoveContextItem}
        onRemoveContextItem={onRemoveContextItem}
        onSubmit={vi.fn()}
      />,
    )

    expect(screen.getByText("引用消息 · 用户")).toBeTruthy()
    expect(screen.getByText(/Diff 产物/)).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "下移上下文 用户" }))
    fireEvent.click(screen.getByRole("button", { name: "移除上下文 Git Diff" }))

    expect(onMoveContextItem).toHaveBeenCalledWith("message:message-1", "down")
    expect(onRemoveContextItem).toHaveBeenCalledWith("diff:diff-1")
  })

  it("builds contextItems payload while preserving legacy context fields", () => {
    const payload = buildComposerMessageContext([
      contextItemFromArtifact(contextArtifact),
      contextItemFromMessage(contextMessage),
    ])

    expect(payload.contextItems).toEqual([
      {
        artifactId: "artifact-diff-1",
        artifactVersionId: null,
        id: "diff:diff-1",
        kind: "artifact",
        selectedText: null,
        summary: "实现登录页",
        title: "Git Diff",
        type: "diff",
      },
      {
        id: "message:message-1",
        kind: "message",
        messageId: "message-1",
        summary: "请基于这个登录需求继续完善。",
        title: "用户",
      },
    ])
    expect(payload.selectedArtifactId).toBe("artifact-diff-1")
    expect(payload.quotedMessage).toEqual({
      contentMd: "请基于这个登录需求继续完善。",
      messageId: "message-1",
      senderType: "user",
    })
  })
})
