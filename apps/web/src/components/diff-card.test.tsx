import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { createElement } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { sampleDiffArtifact } from "./__fixtures__/sample-diff"
import { DiffCard } from "./diff-card"
import { setTheme } from "@/lib/theme"

vi.mock("./local-diff-editor", () => ({
  LocalDiffEditor: ({
    modified,
    original,
    theme,
  }: {
    modified?: string
    original?: string
    theme?: string
  }) => (
    <div data-testid="monaco-diff-editor" data-theme={theme}>
      <pre>{original}</pre>
      <pre>{modified}</pre>
    </div>
  ),
}))

afterEach(() => {
  cleanup()
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe("DiffCard", () => {
  it("updates an open read-only editor when the workbench theme changes", () => {
    render(<DiffCard diff={sampleDiffArtifact} />)
    fireEvent.click(screen.getByRole("button", { name: "展开 Diff" }))
    fireEvent.click(screen.getByRole("button", { name: "并排对比" }))
    expect(screen.getByTestId("monaco-diff-editor").getAttribute("data-theme")).toBe("vs")
    act(() => setTheme("dark"))
    expect(screen.getByTestId("monaco-diff-editor").getAttribute("data-theme")).toBe("vs-dark")
    act(() => setTheme("light"))
    expect(screen.getByTestId("monaco-diff-editor").getAttribute("data-theme")).toBe("vs")
  })
  it("shows an immediate patch and offers read-only Monaco inspection", () => {
    render(createElement(DiffCard, { diff: sampleDiffArtifact }))

    expect(screen.getByText("Git Diff")).toBeTruthy()
    expect(screen.getByText(/1 个文件变更/)).toBeTruthy()
    expect(screen.getByText(/\+2/)).toBeTruthy()
    expect(screen.getByText(/-1/)).toBeTruthy()
    expect(screen.getByText("apps/demo/src/App.tsx")).toBeTruthy()
    expect(screen.queryByTestId("monaco-diff-editor")).toBeNull()

    fireEvent.click(screen.getByRole("button", { name: "展开 Diff" }))
    expect(screen.getByLabelText("代码补丁").textContent).toContain("+      <h1>Welcome back</h1>")
    expect(screen.queryByTestId("monaco-diff-editor")).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "并排对比" }))
    expect(screen.getByTestId("monaco-diff-editor")).toBeTruthy()
    expect(screen.getByText(/Welcome back/)).toBeTruthy()
    expect(screen.getByText(/Continue/)).toBeTruthy()
  })
})
