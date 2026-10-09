import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { createElement } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { samplePreviewArtifact } from "./__fixtures__/sample-preview"
import { sampleReviewArtifact } from "./__fixtures__/sample-review"
import { PreviewCard, PreviewPanel } from "./preview-card"

afterEach(() => cleanup())

describe("PreviewCard", () => {
  it("shows status, URL, port, last checked time, and action buttons", () => {
    const onCreateDeploy = vi.fn()
    const onOpen = vi.fn()
    const onRefresh = vi.fn()
    const onStop = vi.fn()

    render(
      createElement(PreviewCard, {
        onCreateDeploy,
        onOpen,
        onRefresh,
        onStop,
        preview: samplePreviewArtifact,
      }),
    )

    expect(screen.getByText("Vite React 预览")).toBeTruthy()
    expect(screen.getByText("健康")).toBeTruthy()
    expect(screen.getByText("http://127.0.0.1:5173")).toBeTruthy()
    expect(screen.getByText("5173")).toBeTruthy()
    const checkTime = document.querySelector("time")!
    expect(checkTime.dateTime).toBe("2026-05-15T10:30:00.000Z")
    expect(checkTime.title).toContain("原始值：2026-05-15T10:30:00Z")
    expect(checkTime.closest("dd")?.textContent).toContain("最近检查：")

    fireEvent.click(screen.getByRole("button", { name: "打开预览" }))
    fireEvent.click(screen.getByRole("button", { name: "刷新预览" }))
    fireEvent.click(screen.getByRole("button", { name: "创建部署卡片" }))
    fireEvent.click(screen.getByRole("button", { name: "停止预览" }))

    expect(onOpen).toHaveBeenCalledWith(samplePreviewArtifact)
    expect(onRefresh).toHaveBeenCalledWith("run-1")
    expect(onCreateDeploy).toHaveBeenCalledWith("preview-1")
    expect(onStop).toHaveBeenCalledWith("preview-1")
  })

  it("opens the preview URL in the right-side panel iframe", () => {
    const onClose = vi.fn()
    const onRefresh = vi.fn()

    render(
      createElement(PreviewPanel, {
        artifactItems: [
          {
            artifact: samplePreviewArtifact,
            id: "preview-asset",
            kind: "preview",
            taskRunId: "run-1",
            taskTitle: "Build the Vite React login page",
          },
        ],
        frameKey: 2,
        onClose,
        onRefresh,
        selectedArtifactId: "preview-asset",
      }),
    )

    const frame = screen.getByTitle("Vite React 预览")
    expect(frame.getAttribute("src")).toBe("http://127.0.0.1:5173")
    expect(frame.getAttribute("sandbox")).toBe("allow-forms allow-same-origin allow-scripts")
    expect(frame.getAttribute("referrerpolicy")).toBe("no-referrer")
    expect(frame.getAttribute("allow")).toBe(
      "camera 'none'; microphone 'none'; geolocation 'none'; payment 'none'; usb 'none'; clipboard-read 'none'; clipboard-write 'none'",
    )
    for (const forbiddenToken of [
      "allow-downloads",
      "allow-modals",
      "allow-popups",
      "allow-popups-to-escape-sandbox",
      "allow-pointer-lock",
      "allow-presentation",
      "allow-top-navigation",
      "allow-top-navigation-by-user-activation",
    ]) {
      expect(frame.getAttribute("sandbox")?.split(" ")).not.toContain(forbiddenToken)
    }
    expect(screen.getAllByText("127.0.0.1:5173").length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole("button", { name: "刷新面板" }))
    fireEvent.click(screen.getByRole("button", { name: "关闭产物" }))

    expect(onRefresh).toHaveBeenCalledWith("run-1")
    expect(onClose).toHaveBeenCalled()
  })

  it("keeps unhealthy preview artifacts as diagnostics instead of loading a dead iframe", () => {
    const onOpen = vi.fn()

    render(
      createElement(PreviewPanel, {
        artifactItems: [
          {
            artifact: {
              ...samplePreviewArtifact,
              healthStatus: "unhealthy",
              processId: null,
              status: "failed",
              statusReason:
                "Preview process exited before becoming healthy. Recent preview output: Cannot find native binding.",
            },
            id: "preview-asset",
            kind: "preview",
            taskRunId: "run-1",
            taskTitle: "Build the Vite React login page",
          },
        ],
        frameKey: 2,
        onOpenPreview: onOpen,
        selectedArtifactId: "preview-asset",
      }),
    )

    expect(screen.queryByTitle("Vite React 预览")).toBeNull()
    expect(screen.getByText("预览未运行")).toBeTruthy()
    expect(screen.getByText(/Cannot find native binding/)).toBeTruthy()
    const openButton = screen.getByRole("button", { name: "打开预览" })
    expect((openButton as HTMLButtonElement).disabled).toBe(true)
    expect(onOpen).not.toHaveBeenCalled()
  })

  it("renders review artifacts in the right-side panel", () => {
    render(
      createElement(PreviewPanel, {
        artifactItems: [
          {
            artifact: sampleReviewArtifact,
            id: "review-asset",
            kind: "review",
            taskRunId: "run-1",
            taskTitle: "Build the Vite React login page",
          },
        ],
        frameKey: 1,
        selectedArtifactId: "review-asset",
      }),
    )

    expect(screen.getAllByText("评审报告").length).toBeGreaterThan(0)
    expect(screen.getByText("仅供参考 · scripted_mock")).toBeTruthy()
    expect(
      screen.getByText("脚本评审通过 1 个变更文件，风险较低。"),
    ).toBeTruthy()
    expect(screen.getAllByText("通过").length).toBeGreaterThan(0)
  })

  it("keeps the actual native assessment, provenance and test boundary after rerender", () => {
    const props = {
      artifactItems: [{
        artifact: {
          ...sampleReviewArtifact, adapterType: "claude_code", title: "Native model review",
          status: "warning", riskLevel: "low", summary: "发现一个模型评审问题。",
          findings: [{ severity: "low", file: "apps/demo/src/App.tsx", line: 7, message: "按钮需要可访问性说明。" }],
          suggestedChanges: ["补充按钮说明。"],
          nativeReceipt: {
            schemaVersion: "agenthub.native_review.v1", taskRunId: "run-1", adapterRunId: "claude-1",
            targetId: "demo-frontend", inputFingerprint: "a".repeat(64), outputSha256: "b".repeat(64),
            validation: "not_run" as const, assessmentKind: "advisory_static_review", boundFileCount: 3,
            files: { "apps/demo/src/App.tsx": { sha256: "c".repeat(64), bytes: 200 } },
          },
        },
        id: "native-asset", kind: "review" as const, taskRunId: "run-1", taskTitle: "Read-only native review",
      }],
      frameKey: 1, selectedArtifactId: "native-asset",
    }
    const view = render(createElement(PreviewPanel, props))
    view.rerender(createElement(PreviewPanel, { ...props, frameKey: 2 }))
    expect(screen.getByText("模型评审 · claude_code · 仅供参考")).toBeTruthy()
    expect(screen.getByText("只读静态评审 · 未运行测试，结论不代表功能验收通过。")).toBeTruthy()
    expect(screen.getByText("发现一个模型评审问题。")).toBeTruthy()
    expect(screen.getByText("按钮需要可访问性说明。")).toBeTruthy()
    expect(screen.getByText("补充按钮说明。")).toBeTruthy()
    expect(screen.getByText("低 · apps/demo/src/App.tsx:7")).toBeTruthy()
    expect(screen.getByText(/文件版本 aaaaaaaaaaaa · 原生输出 bbbbbbbbbbbb/)).toBeTruthy()
    expect(screen.queryByText("仅供参考 · scripted_mock")).toBeNull()
  })

  it("translates review findings and suggestions in the right-side panel", () => {
    render(
      createElement(PreviewPanel, {
        artifactItems: [
          {
            artifact: {
              ...sampleReviewArtifact,
              findings: [
                {
                  message:
                    "External target external-backend-pomodoro-app has configured check command `python -m py_compile main.py` but no evidence was recorded.",
                  severity: "medium",
                },
              ],
              riskLevel: "medium",
              status: "warning",
              suggestedChanges: [
                "Record check evidence for `python -m py_compile main.py`.",
              ],
              summary:
                "Scripted Review Agent found 2 advisory findings with medium risk.",
            },
            id: "review-asset",
            kind: "review",
            taskRunId: "run-1",
            taskTitle: "Build the Pomodoro backend",
          },
        ],
        frameKey: 1,
        selectedArtifactId: "review-asset",
      }),
    )

    expect(
      screen.getByText("脚本评审发现 2 条建议项，风险等级为中。"),
    ).toBeTruthy()
    expect(screen.getAllByText("中").length).toBeGreaterThan(0)
    expect(
      screen.getByText(
        "外部目标 external-backend-pomodoro-app 配置了检查命令 `python -m py_compile main.py`，但尚未记录验证证据。",
      ),
    ).toBeTruthy()
    expect(
      screen.getByText(
        "记录 `python -m py_compile main.py` 的检查验证证据。",
      ),
    ).toBeTruthy()
  })

  it("shows artifact workbench empty state before evidence is selected", () => {
    render(
      createElement(PreviewPanel, {
        artifactItems: [],
        frameKey: 1,
        selectedArtifactId: null,
      }),
    )

    expect(screen.getByText("证据工作台")).toBeTruthy()
    expect(screen.getByText("等待产物")).toBeTruthy()
    expect(
      screen.queryByText("从任务时间线选择 Diff、评审、预览或部署产物。"),
    ).toBeNull()
    expect(
      screen.queryByText("任务生成 Diff、评审、预览或部署证据后，可在这里查看详情。"),
    ).toBeNull()
  })

  it("renders artifact workbench markdown content and version metadata", () => {
    const onSaveArtifactEdit = vi.fn()
    render(
      createElement(PreviewPanel, {
        artifactItems: [
          {
            artifact: {
              artifactId: "artifact-doc-1",
              artifactType: "markdown_document",
              contentHash: "sha256:artifact",
              createdAt: "2026-06-08T00:00:00Z",
              editable: true,
              rendererKind: "markdown_document",
              safeMeta: { safePath: "docs/change-log.md" },
              status: "ready",
              taskRunId: "run-1",
              title: "Release notes",
              updatedAt: "2026-06-08T00:00:00Z",
              version: 2,
              versions: [
                {
                  artifactId: "artifact-doc-1",
                  changedFiles: [],
                  contentHash: "sha256:version",
                  contentMd: "# Release notes",
                  createdAt: "2026-06-08T00:00:00Z",
                  editorSource: "user",
                  gitBaseRef: null,
                  gitHeadRef: null,
                  id: "version-2",
                  parentArtifactId: null,
                  parentVersionId: "version-1",
                  sourceTaskRunId: "run-1",
                  summary: "Edited release notes.",
                  version: 2,
                },
              ],
            },
            id: "workbench:artifact-doc-1",
            kind: "workbench",
            taskRunId: "run-1",
            taskTitle: "Release notes",
          },
        ],
        frameKey: 1,
        onSaveArtifactEdit,
        selectedArtifactId: "workbench:artifact-doc-1",
      }),
    )

    expect(screen.getByText("Artifact Workbench")).toBeTruthy()
    expect(screen.getAllByText("Markdown 文档").length).toBeGreaterThan(0)
    expect(screen.getByText("# Release notes")).toBeTruthy()
    expect(screen.getAllByText("v2").length).toBeGreaterThan(0)
    expect(screen.getByText("Edited release notes.")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "编辑版本" }))
    const editor = screen.getByLabelText("编辑内容")
    fireEvent.change(editor, { target: { value: "# Updated release notes" } })
    fireEvent.change(screen.getByLabelText("版本摘要"), {
      target: { value: "Updated from UI." },
    })
    fireEvent.click(screen.getByRole("button", { name: "保存版本" }))

    expect(onSaveArtifactEdit).toHaveBeenCalledWith(
      "artifact-doc-1",
      "# Updated release notes",
      "Updated from UI.",
    )
  })

  it("cancels artifact workbench edits without saving", () => {
    const onSaveArtifactEdit = vi.fn()
    render(
      createElement(PreviewPanel, {
        artifactItems: [
          {
            artifact: {
              artifactId: "artifact-doc-1",
              artifactType: "text_document",
              contentHash: "sha256:artifact",
              createdAt: "2026-06-08T00:00:00Z",
              editable: true,
              rendererKind: "text_document",
              safeMeta: {},
              status: "ready",
              taskRunId: "run-1",
              title: "Notes",
              updatedAt: "2026-06-08T00:00:00Z",
              version: 1,
              versions: [
                {
                  artifactId: "artifact-doc-1",
                  changedFiles: [],
                  contentHash: "sha256:version",
                  contentMd: "Original notes",
                  createdAt: "2026-06-08T00:00:00Z",
                  editorSource: "system",
                  gitBaseRef: null,
                  gitHeadRef: null,
                  id: "version-1",
                  parentArtifactId: null,
                  parentVersionId: null,
                  sourceTaskRunId: "run-1",
                  summary: "Original.",
                  version: 1,
                },
              ],
            },
            id: "workbench:artifact-doc-1",
            kind: "workbench",
            taskRunId: "run-1",
            taskTitle: "Notes",
          },
        ],
        frameKey: 1,
        onSaveArtifactEdit,
        selectedArtifactId: "workbench:artifact-doc-1",
      }),
    )

    fireEvent.click(screen.getByRole("button", { name: "编辑版本" }))
    fireEvent.change(screen.getByLabelText("编辑内容"), {
      target: { value: "Changed notes" },
    })
    fireEvent.click(screen.getAllByRole("button", { name: "取消" })[0])

    expect(onSaveArtifactEdit).not.toHaveBeenCalled()
    expect(screen.getByText("Original notes")).toBeTruthy()
  })

  it("renders unknown artifact workbench fallback with safe metadata", () => {
    render(
      createElement(PreviewPanel, {
        artifactItems: [
          {
            artifact: {
              artifactId: "artifact-unknown-1",
              artifactType: "custom_binary",
              contentHash: "sha256:artifact",
              createdAt: "2026-06-08T00:00:00Z",
              editable: false,
              rendererKind: "unknown",
              safeMeta: { label: "opaque artifact" },
              status: "ready",
              taskRunId: "run-1",
              title: "Opaque artifact",
              updatedAt: "2026-06-08T00:00:00Z",
              version: 1,
              versions: [],
            },
            id: "workbench:artifact-unknown-1",
            kind: "workbench",
            taskRunId: "run-1",
            taskTitle: "Opaque artifact",
          },
        ],
        frameKey: 1,
        selectedArtifactId: "workbench:artifact-unknown-1",
      }),
    )

    expect(screen.getAllByText("未知类型").length).toBeGreaterThan(0)
    expect(screen.getByText(/opaque artifact/)).toBeTruthy()
    expect(screen.getByText("尚无版本记录")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "编辑版本" })).toBeNull()
  })
  it("allows closing an empty inspector and toggles the expanded layout", () => {
    const onClose = vi.fn(), onToggleExpand = vi.fn()
    const view = render(<PreviewPanel artifactItems={[]} frameKey={0} selectedArtifactId={null} onClose={onClose} onToggleExpand={onToggleExpand} />)
    fireEvent.click(screen.getByRole("button", { name: "关闭产物" }))
    fireEvent.click(screen.getByRole("button", { name: "展开成果" }))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(onToggleExpand).toHaveBeenCalledTimes(1)
    view.rerender(<PreviewPanel artifactItems={[]} frameKey={0} selectedArtifactId={null} expanded onClose={onClose} onToggleExpand={onToggleExpand} />)
    fireEvent.click(screen.getByRole("button", { name: "恢复布局" }))
    expect(onToggleExpand).toHaveBeenCalledTimes(2)
  })

})
