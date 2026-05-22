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
    expect(screen.getByText("最近检查：5月15日 10:30")).toBeTruthy()

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
    expect(screen.getAllByText("127.0.0.1:5173").length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole("button", { name: "刷新面板" }))
    fireEvent.click(screen.getByRole("button", { name: "关闭产物" }))

    expect(onRefresh).toHaveBeenCalledWith("run-1")
    expect(onClose).toHaveBeenCalled()
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

    expect(screen.getAllByText("Review Agent report").length).toBeGreaterThan(0)
    expect(screen.getByText("Advisory only · scripted_mock")).toBeTruthy()
    expect(
      screen.getByText("Scripted Review Agent passed 1 changed file with low risk."),
    ).toBeTruthy()
    expect(screen.getAllByText("通过").length).toBeGreaterThan(0)
  })
})
