import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { createElement } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { sampleDiffArtifact } from "./__fixtures__/sample-diff"
import { DiffCard } from "./diff-card"

vi.mock("@monaco-editor/react", () => ({
  DiffEditor: ({
    modified,
    original,
  }: {
    modified?: string
    original?: string
  }) => (
    <div data-testid="monaco-diff-editor">
      <pre>{original}</pre>
      <pre>{modified}</pre>
    </div>
  ),
}))

afterEach(() => cleanup())

describe("DiffCard", () => {
  it("shows changed files, stats, and expands into Monaco file inspection", () => {
    render(createElement(DiffCard, { diff: sampleDiffArtifact }))

    expect(screen.getByText("Git Diff")).toBeTruthy()
    expect(screen.getByText(/1 个文件变更/)).toBeTruthy()
    expect(screen.getByText(/\+2/)).toBeTruthy()
    expect(screen.getByText(/-1/)).toBeTruthy()
    expect(screen.getByText("apps/demo/src/App.tsx")).toBeTruthy()
    expect(screen.queryByTestId("monaco-diff-editor")).toBeNull()

    fireEvent.click(screen.getByRole("button", { name: "展开 Diff" }))

    expect(screen.getByTestId("monaco-diff-editor")).toBeTruthy()
    expect(screen.getByText(/Welcome back/)).toBeTruthy()
    expect(screen.getByText(/Continue/)).toBeTruthy()
  })
})
