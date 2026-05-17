import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { createElement } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { samplePreviewArtifact } from "./__fixtures__/sample-preview"
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

    expect(screen.getByText("Vite React preview")).toBeTruthy()
    expect(screen.getByText("healthy")).toBeTruthy()
    expect(screen.getByText("http://127.0.0.1:5173")).toBeTruthy()
    expect(screen.getByText("5173")).toBeTruthy()
    expect(screen.getByText("Last checked: May 15, 10:30")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "Open preview" }))
    fireEvent.click(screen.getByRole("button", { name: "Refresh preview" }))
    fireEvent.click(screen.getByRole("button", { name: "Create deploy card" }))
    fireEvent.click(screen.getByRole("button", { name: "Stop preview" }))

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
        frameKey: 2,
        onClose,
        onRefresh,
        preview: samplePreviewArtifact,
      }),
    )

    const frame = screen.getByTitle("Vite React preview")
    expect(frame.getAttribute("src")).toBe("http://127.0.0.1:5173")
    expect(screen.getByText("127.0.0.1:5173")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "Refresh panel" }))
    fireEvent.click(screen.getByRole("button", { name: "Close preview" }))

    expect(onRefresh).toHaveBeenCalledWith("run-1")
    expect(onClose).toHaveBeenCalled()
  })
})
