import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import type { EditorProps } from "@monaco-editor/react"
import { LocalCodeEditor } from "./local-code-editor"

const { renderEditor } = vi.hoisted(() => ({ renderEditor: vi.fn() }))
vi.mock("@/lib/load-local-monaco", () => ({ loadLocalMonaco: vi.fn().mockResolvedValue({}) }))
vi.mock("@monaco-editor/react", () => ({ default: (props: EditorProps) => { renderEditor(props); return <div data-testid="source-editor" /> } }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it("quotes an exact textarea selection without changing the draft and rejects stale selections", async () => {
  const quote = vi.fn(), change = vi.fn()
  const props = { value: "const title = '测试';\nnext()", path: "src/App.tsx", disabled: false, onChange: change, onQuote: quote }
  const view = render(<LocalCodeEditor {...props} />)
  fireEvent.click(screen.getByRole("button", { name: "纯文本模式" }))
  const input = screen.getByRole("textbox", { name: "完整源码" }) as HTMLTextAreaElement
  input.setSelectionRange(6, 18)
  fireEvent.select(input)
  fireEvent.click(screen.getByRole("button", { name: "引用选中代码" }))
  expect(quote).toHaveBeenCalledExactlyOnceWith(props.value.slice(6, 18))
  expect(change).not.toHaveBeenCalled()
  expect((screen.getByRole("button", { name: "引用选中代码" }) as HTMLButtonElement).disabled).toBe(true)
  input.setSelectionRange(0, 5); fireEvent.select(input)
  view.rerender(<LocalCodeEditor {...props} value="different" />)
  expect((screen.getByRole("button", { name: "引用选中代码" }) as HTMLButtonElement).disabled).toBe(true)
  await act(async () => {})
})

it("requires a smaller selection rather than silently truncating over-budget code", async () => {
  render(<LocalCodeEditor value={"x".repeat(2401)} path="source.ts" disabled={false} onChange={vi.fn()} onQuote={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "纯文本模式" }))
  const input = screen.getByRole("textbox", { name: "完整源码" }) as HTMLTextAreaElement
  input.setSelectionRange(0, 2401); fireEvent.select(input)
  expect(screen.getByText(/选区超过 2400/)).toBeTruthy()
  expect((screen.getByRole("button", { name: "引用选中代码" }) as HTMLButtonElement).disabled).toBe(true)
  await act(async () => {})
})

it("reads native editor selection and disposes its listener with the editor models", async () => {
  const quote = vi.fn()
  const view = render(<LocalCodeEditor value="abc\ndef" path="source.ts" disabled={false} onChange={vi.fn()} onQuote={quote} />)
  await screen.findByTestId("source-editor")
  let select!: () => void
  const dispose = vi.fn(), modelDispose = vi.fn()
  const editor = { onDidChangeCursorSelection: (callback: () => void) => { select = callback; return { dispose } },
    getSelection: () => ({ startLineNumber: 2, endLineNumber: 2 }),
    getModel: () => ({ getValueInRange: () => "def", dispose: modelDispose }), setModel: vi.fn() }
  const props = renderEditor.mock.lastCall![0] as EditorProps
  act(() => props.onMount!(editor as unknown as Parameters<NonNullable<EditorProps["onMount"]>>[0], {} as Parameters<NonNullable<EditorProps["onMount"]>>[1]))
  act(() => select())
  fireEvent.click(screen.getByRole("button", { name: "引用选中代码" }))
  expect(quote).toHaveBeenCalledExactlyOnceWith("def")
  view.unmount()
  expect(dispose).toHaveBeenCalledTimes(1)
  expect(modelDispose).toHaveBeenCalledTimes(1)
})
