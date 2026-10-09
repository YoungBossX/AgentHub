import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import type { DiffEditorProps } from "@monaco-editor/react"

import { LocalDiffEditor } from "./local-diff-editor"
import { loadLocalMonaco } from "@/lib/load-local-monaco"

vi.mock("@/lib/load-local-monaco", () => ({ loadLocalMonaco: vi.fn() }))
const { renderEditor } = vi.hoisted(() => ({ renderEditor: vi.fn() }))
vi.mock("@monaco-editor/react", () => ({ DiffEditor: (props: DiffEditorProps) => renderEditor(props) }))

beforeEach(() => {
  vi.mocked(loadLocalMonaco).mockReset()
  renderEditor.mockReset().mockImplementation(({ original, modified, theme }: DiffEditorProps) =>
    <div data-testid="editor" data-theme={theme}>{original} → {modified}</div>)
})
afterEach(cleanup)

it("keeps the patch while loading and passes the latest content and theme after readiness", async () => {
  let ready!: () => void
  vi.mocked(loadLocalMonaco).mockImplementation(() => new Promise(resolve => { ready = () => resolve({}) }))
  const view = render(<LocalDiffEditor original="before" modified="old" theme="vs" loading={<pre>Patch</pre>} />)
  expect(screen.queryByTestId("editor")).toBeNull()
  expect(screen.getByText("Patch")).toBeTruthy()
  view.rerender(<LocalDiffEditor original="before" modified="latest" theme="vs-dark" loading={<pre>Patch</pre>} />)
  await act(async () => ready())
  expect(screen.getByTestId("editor").textContent).toBe("before → latest")
  expect(screen.getByTestId("editor").getAttribute("data-theme")).toBe("vs-dark")
  expect(loadLocalMonaco).toHaveBeenCalledTimes(1)
})

it("handles a failed local chunk without hiding the patch and lets the user retry", async () => {
  vi.mocked(loadLocalMonaco).mockRejectedValueOnce(new Error("chunk unavailable")).mockResolvedValueOnce({})
  render(<LocalDiffEditor loading={<pre>Retained patch</pre>} />)
  await screen.findByRole("status")
  expect(screen.getByText("Retained patch")).toBeTruthy()
  expect(screen.queryByTestId("editor")).toBeNull()
  fireEvent.click(screen.getByRole("button", { name: "重试加载" }))
  await screen.findByTestId("editor")
  expect(screen.queryByRole("status")).toBeNull()
  expect(loadLocalMonaco).toHaveBeenCalledTimes(2)
})

it("ignores completion after unmount while a new instance can finish loading", async () => {
  let reject!: (error: Error) => void
  vi.mocked(loadLocalMonaco).mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail }))
    .mockResolvedValueOnce({})
  const view = render(<LocalDiffEditor loading={<pre>Old patch</pre>} />)
  view.unmount()
  render(<LocalDiffEditor modified="new" />)
  await act(async () => reject(new Error("old request failed")))
  await waitFor(() => expect(screen.getByTestId("editor").textContent).toContain("new"))
  expect(screen.queryByRole("status")).toBeNull()
})

it("detaches private models before releasing them when switching away from the diff", async () => {
  vi.mocked(loadLocalMonaco).mockResolvedValueOnce({})
  const view = render(<LocalDiffEditor />)
  await screen.findByTestId("editor")
  const props = renderEditor.mock.lastCall![0] as DiffEditorProps
  const original = { dispose: vi.fn(() => { expect(attached).toBeNull() }) }
  const modified = { dispose: vi.fn(() => { expect(attached).toBeNull() }) }
  let attached: { original: typeof original; modified: typeof modified } | null = { original, modified }
  const editor = { getModel: () => attached, setModel: () => { attached = null } }
  props.onMount!(editor as unknown as Parameters<NonNullable<DiffEditorProps["onMount"]>>[0], {} as Parameters<NonNullable<DiffEditorProps["onMount"]>>[1])
  expect(props.keepCurrentOriginalModel).toBe(true)
  expect(props.keepCurrentModifiedModel).toBe(true)
  view.unmount()
  expect(original.dispose).toHaveBeenCalledTimes(1)
  expect(modified.dispose).toHaveBeenCalledTimes(1)
})
