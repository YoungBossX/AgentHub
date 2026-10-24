import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { createRef } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  buildComposerMessageContext,
  contextItemFromArtifact,
  contextItemFromCode,
  contextItemFromMessage,
  MessageComposer,
} from "./message-composer"
import { sampleDeploymentArtifact } from "./__fixtures__/sample-deployment"
import type { ArtifactPanelItem } from "@/components/preview-card"
import type { ChatMessage } from "@/lib/api"

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe("自适应消息输入", () => {
  const props = { contextItems: [], draft: "中文需求", isPending: false,
    onClearContext: vi.fn(), onDraftChange: vi.fn(), onMoveContextItem: vi.fn(),
    onRemoveContextItem: vi.fn(), onSubmit: vi.fn() }

  it("随恢复、粘贴与清空草稿增高和回缩，同时保留外部焦点引用", () => {
    let contentHeight = 64
    vi.spyOn(HTMLTextAreaElement.prototype, "scrollHeight", "get").mockImplementation(() => contentHeight)
    const inputRef = createRef<HTMLTextAreaElement>()
    const view = render(<MessageComposer {...props} inputRef={inputRef} />)
    const textarea = screen.getByRole("textbox", { name: "消息" }) as HTMLTextAreaElement
    expect(inputRef.current).toBe(textarea)
    expect(textarea.style.height).toBe("64px")
    contentHeight = 480
    view.rerender(<MessageComposer {...props} draft={"长需求\n".repeat(20)} inputRef={inputRef} />)
    expect(textarea.style.height).toBe("480px")
    textarea.setSelectionRange(2, 4)
    expect(textarea.selectionStart).toBe(2)
    inputRef.current?.focus()
    expect(document.activeElement).toBe(textarea)
    contentHeight = 64
    view.rerender(<MessageComposer {...props} draft="" inputRef={inputRef} />)
    expect(textarea.style.height).toBe("64px")
    view.unmount()
    expect(inputRef.current).toBeNull()
  })

  it("宽度变化重新测量，单纯高度变化不形成观察循环，卸载时释放观察器", () => {
    let contentHeight = 90
    vi.spyOn(HTMLTextAreaElement.prototype, "scrollHeight", "get").mockImplementation(() => contentHeight)
    let callback: ResizeObserverCallback = () => {}
    const disconnect = vi.fn()
    vi.stubGlobal("ResizeObserver", class {
      constructor(next: ResizeObserverCallback) { callback = next }
      observe = vi.fn()
      disconnect = disconnect
    })
    const view = render(<MessageComposer {...props} />)
    const textarea = screen.getByRole("textbox", { name: "消息" }) as HTMLTextAreaElement
    const resize = (width: number) => callback([{ contentRect: { width } } as ResizeObserverEntry], {} as ResizeObserver)
    contentHeight = 190
    resize(240)
    expect(textarea.style.height).toBe("190px")
    contentHeight = 250
    resize(240)
    expect(textarea.style.height).toBe("190px")
    resize(180)
    expect(textarea.style.height).toBe("250px")
    view.unmount()
    expect(disconnect).toHaveBeenCalledOnce()
  })

  it("无 ResizeObserver 时仍支持窗口变化与回调引用", () => {
    vi.stubGlobal("ResizeObserver", undefined)
    let contentHeight = 70
    vi.spyOn(HTMLTextAreaElement.prototype, "scrollHeight", "get").mockImplementation(() => contentHeight)
    const inputRef = vi.fn()
    const view = render(<MessageComposer {...props} inputRef={inputRef} />)
    const textarea = screen.getByRole("textbox", { name: "消息" }) as HTMLTextAreaElement
    expect(inputRef).toHaveBeenCalledWith(textarea)
    contentHeight = 140
    fireEvent(window, new Event("resize"))
    expect(textarea.style.height).toBe("140px")
    view.unmount()
    expect(inputRef).toHaveBeenLastCalledWith(null)
  })

  it("短小屏幕用可展开摘要保留上下文，展开与收起不改变草稿或待发送内容", () => {
    vi.stubGlobal("innerWidth", 390)
    vi.stubGlobal("innerHeight", 360)
    vi.stubGlobal("visualViewport", undefined)
    const context = [{ id: "note", kind: "note" as const, title: "需要保留的引用", summary: "真实引用内容" }]
    render(<MessageComposer {...props} contextItems={context} />)
    const toggle = screen.getByRole("button", { name: "上下文与附件" })
    expect(toggle.getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByRole("button", { name: "移除上下文 需要保留的引用" })).toBeNull()
    fireEvent.click(toggle)
    expect(screen.getByRole("button", { name: "移除上下文 需要保留的引用" })).toBeTruthy()
    expect(toggle.getAttribute("aria-expanded")).toBe("true")
    fireEvent.click(toggle)
    expect(screen.getByRole("textbox", { name: "消息" }).getAttribute("aria-label")).toBe("消息")
    expect((screen.getByRole("textbox", { name: "消息" }) as HTMLTextAreaElement).value).toBe(props.draft)
    expect(buildComposerMessageContext(context).contextItems).toHaveLength(1)
  })
})

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

const deploymentContextArtifact: ArtifactPanelItem = {
  artifact: sampleDeploymentArtifact,
  id: `deployment:${sampleDeploymentArtifact.id}`,
  kind: "deployment",
  taskRunId: sampleDeploymentArtifact.taskRunId,
  taskTitle: "部署演示应用",
}

const workbenchContextArtifact: ArtifactPanelItem = {
  artifact: {
    artifactId: "artifact-doc-1",
    artifactType: "markdown_document",
    contentHash: "hash-v2",
    createdAt: "2026-06-08T00:00:00Z",
    editable: true,
    rendererKind: "markdown",
    safeMeta: {},
    status: "ready",
    taskRunId: "run-doc-123456",
    title: "发布说明",
    updatedAt: "2026-06-08T00:00:00Z",
    version: 2,
    versions: [
      {
        artifactId: "artifact-doc-1",
        changedFiles: [],
        contentHash: "hash-v2",
        contentMd: "## 发布说明",
        createdAt: "2026-06-08T00:00:00Z",
        editorSource: "user_edit",
        gitBaseRef: null,
        gitHeadRef: null,
        id: "version-2",
        parentArtifactId: null,
        parentVersionId: "version-1",
        sourceTaskRunId: "run-doc-123456",
        summary: "用户选中的文档段落",
        version: 2,
      },
    ],
  },
  id: "workbench:artifact-doc-1",
  kind: "workbench",
  taskRunId: "run-doc-123456",
  taskTitle: "编辑发布说明",
}

describe("MessageComposer", () => {
  function input() {
    const submit = vi.fn((event: React.FormEvent) => event.preventDefault())
    render(<MessageComposer contextItems={[]} draft="中文任务" isPending={false}
      onClearContext={vi.fn()} onDraftChange={vi.fn()} onMoveContextItem={vi.fn()}
      onRemoveContextItem={vi.fn()} onSubmit={submit} />)
    vi.spyOn(HTMLFormElement.prototype, "requestSubmit").mockImplementation(function (this: HTMLFormElement) {
      this.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }))
    })
    return { textbox: screen.getByRole("textbox", { name: "消息" }), submit }
  }

  it("blocks Enter through IME confirmation and the full 500ms guard interval", () => {
    vi.useFakeTimers()
    const { textbox, submit } = input()
    fireEvent.compositionStart(textbox)
    fireEvent.keyDown(textbox, { key: "Enter" })
    expect(submit).not.toHaveBeenCalled()
    fireEvent.compositionEnd(textbox)
    fireEvent.keyDown(textbox, { key: "Enter" })
    vi.advanceTimersByTime(499)
    fireEvent.keyDown(textbox, { key: "Enter" })
    expect(submit).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    fireEvent.keyDown(textbox, { key: "Enter" })
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it.each([{ isComposing: true }, { keyCode: 229 }])("blocks native IME Enter %j", (native) => {
    const { textbox, submit } = input()
    fireEvent.keyDown(textbox, { key: "Enter", ...native })
    expect(submit).not.toHaveBeenCalled()
    fireEvent.keyDown(textbox, { key: "Enter", shiftKey: true })
    expect(submit).not.toHaveBeenCalled()
    fireEvent.keyDown(textbox, { key: "Enter" })
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it("preserves quoted code and draft provenance in the outgoing context", () => {
    const text = "  const title = '选区';\n"
    const selected = contextItemFromCode(contextArtifact, "src/App.tsx", text)
    const payload = buildComposerMessageContext([selected])
    expect(payload.selectedText).toBe(text)
    expect(payload.selectedArtifactId).toBe("artifact-diff-1")
    expect(payload.contextItems).toEqual([expect.objectContaining({
      kind: "selected_text", selectedText: text, artifactId: "artifact-diff-1",
      metadata: { path: "src/App.tsx", source: "editor_draft" },
    })])
  })
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

  it("rehearses combined context payload for freeze review", () => {
    const payload = buildComposerMessageContext([
      contextItemFromArtifact(deploymentContextArtifact),
      contextItemFromArtifact(contextArtifact),
      contextItemFromArtifact(workbenchContextArtifact),
      contextItemFromMessage(contextMessage),
    ])

    expect(payload.contextItems).toEqual([
      expect.objectContaining({
        artifactId: sampleDeploymentArtifact.artifactId,
        id: `deployment:${sampleDeploymentArtifact.id}`,
        kind: "deployment",
        title: sampleDeploymentArtifact.title,
        type: "deployment",
      }),
      expect.objectContaining({
        artifactId: "artifact-diff-1",
        id: "diff:diff-1",
        kind: "artifact",
        type: "diff",
      }),
      expect.objectContaining({
        artifactId: "artifact-doc-1",
        artifactVersionId: "version-2",
        id: "workbench:artifact-doc-1",
        kind: "artifact",
        summary: "用户选中的文档段落",
        type: "markdown_document",
      }),
      expect.objectContaining({
        id: "message:message-1",
        kind: "message",
        messageId: "message-1",
      }),
    ])
    expect(payload.selectedArtifactId).toBe(sampleDeploymentArtifact.artifactId)
    expect(payload.quotedMessage).toEqual(
      expect.objectContaining({ messageId: "message-1" }),
    )
  })
})
