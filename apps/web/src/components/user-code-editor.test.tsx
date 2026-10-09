import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { UserCodeEditor } from "./user-code-editor"
import { CodeEditProvider, UserCodeEditStatus } from "./user-code-edit-context"
import * as api from "@/lib/api"

vi.mock("@/lib/api", () => ({ loadCodeEditSource: vi.fn(), listCodeEdits: vi.fn(), prepareCodeEdit: vi.fn(), applyCodeEdit: vi.fn(), resolveCodeEdit: vi.fn() }))
vi.mock("./local-code-editor", () => ({ LocalCodeEditor: ({ value, onChange, disabled }: { value: string; onChange: (value: string) => void; disabled: boolean }) =>
  <textarea aria-label="完整源码" disabled={disabled} value={value} onChange={event => onChange(event.target.value)} /> }))
const path = "apps/demo/src/App.tsx"
const source = { path, content: "complete current source\n", sha256: "a".repeat(64), binding: "b".repeat(64), head: "c", targetId: "demo-frontend" }
const operation = { id: "operation", state: "prepared", actor: "user" as const, sourceArtifactId: "diff", targetId: "demo-frontend", patch: "-old\n+new", files: [], reason: null, createdAt: "now", updatedAt: "now" }
function view(sessionId = "session") {
  return <CodeEditProvider backendUrl="http://api" sessionId={sessionId}><UserCodeEditor artifactId="diff" paths={[path]} /><UserCodeEditStatus /></CodeEditProvider>
}
async function openLoaded() {
  fireEvent.click(screen.getByText("编辑完整源码 / 应用补丁"))
  fireEvent.click(screen.getByText("读取完整源码"))
  const input = await screen.findByLabelText("完整源码")
  expect((input as HTMLTextAreaElement).value).toBe("complete current source\n")
}
beforeEach(() => {
  sessionStorage.clear(); vi.resetAllMocks()
  vi.mocked(api.listCodeEdits).mockResolvedValue([])
  vi.mocked(api.loadCodeEditSource).mockResolvedValue(source)
  vi.mocked(api.prepareCodeEdit).mockResolvedValue(operation)
  vi.mocked(api.applyCodeEdit).mockResolvedValue({ ...operation, state: "applied" })
})
afterEach(cleanup)

it("requires loading full current source and reviewing a proposed difference before apply", async () => {
  render(view()); await openLoaded()
  fireEvent.change(screen.getByLabelText("完整源码"), { target: { value: "my full source\n" } })
  expect(api.applyCodeEdit).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText("检查并生成差异"))
  await screen.findByLabelText("拟应用差异")
  expect(api.prepareCodeEdit).toHaveBeenCalledWith("http://api", "session", expect.objectContaining({
    sourceArtifactId: "diff", path, content: "my full source\n", expectedSha256: source.sha256, expectedBinding: source.binding,
  }))
  fireEvent.click(screen.getByText("应用以上差异"))
  await screen.findByText(/文件已更新/)
  expect(api.applyCodeEdit).toHaveBeenCalledTimes(1)
})

it("keeps draft and operation identity after a lost prepare response, and across reload", async () => {
  const first = render(view()); await openLoaded()
  fireEvent.change(screen.getByLabelText("完整源码"), { target: { value: "retained" } })
  vi.mocked(api.prepareCodeEdit).mockRejectedValueOnce(new Error("network failed"))
  fireEvent.click(screen.getByText("检查并生成差异")); await screen.findByRole("alert")
  const id = vi.mocked(api.prepareCodeEdit).mock.calls[0][2].operationId
  first.unmount(); render(view())
  fireEvent.click(screen.getByText("编辑完整源码 / 应用补丁"))
  expect(screen.getByLabelText("完整源码").getAttribute("aria-label")).toBe("完整源码")
  expect((screen.getByLabelText("完整源码") as HTMLTextAreaElement).value).toBe("retained")
  fireEvent.click(screen.getByText("检查并生成差异")); await screen.findByLabelText("拟应用差异")
  expect(vi.mocked(api.prepareCodeEdit).mock.calls[1][2].operationId).toBe(id)
})

it("disables duplicate submissions and ignores results after switching Sessions", async () => {
  let finish!: (value: api.CodeEditOperation) => void
  vi.mocked(api.prepareCodeEdit).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  const rendered = render(view()); await openLoaded()
  const submit = screen.getByText("检查并生成差异")
  fireEvent.click(submit); fireEvent.click(submit)
  expect(api.prepareCodeEdit).toHaveBeenCalledTimes(1)
  rendered.rerender(view("other"))
  await act(async () => finish(operation))
  expect(screen.queryByLabelText("拟应用差异")).toBeNull()
  expect(screen.queryByDisplayValue("complete current source\n")).toBeNull()
})

it("keeps source draft on a conflict and exposes a separate patch input", async () => {
  vi.mocked(api.applyCodeEdit).mockResolvedValue({ ...operation, state: "conflict" })
  render(view()); await openLoaded()
  fireEvent.click(screen.getByText("检查并生成差异")); await screen.findByText("应用以上差异")
  fireEvent.click(screen.getByText("应用以上差异")); await screen.findByText(/用户修改 · 版本冲突/)
  expect((screen.getByLabelText("完整源码") as HTMLTextAreaElement).value).toBe(source.content)
  fireEvent.click(screen.getByText("输入补丁"))
  fireEvent.change(screen.getByLabelText("待应用补丁"), { target: { value: "a patch" } })
  fireEvent.click(screen.getByText("检查并生成差异")); await screen.findByText("应用以上差异")
  expect(vi.mocked(api.prepareCodeEdit).mock.lastCall?.[2]).toEqual(expect.objectContaining({ patch: "a patch" }))
  expect(vi.mocked(api.prepareCodeEdit).mock.lastCall?.[2]).not.toHaveProperty("path")
})

it("recovers an applied result by saved operation ID and labels current preview provenance", async () => {
  const initial = render(view()); await openLoaded()
  fireEvent.click(screen.getByText("检查并生成差异")); await screen.findByText("应用以上差异")
  const id = vi.mocked(api.prepareCodeEdit).mock.lastCall![2].operationId
  initial.unmount()
  vi.mocked(api.listCodeEdits).mockResolvedValue([{ ...operation, id, state: "applied" }])
  render(view()); fireEvent.click(screen.getByText("编辑完整源码 / 应用补丁"))
  await screen.findByText(/文件已更新/)
  expect(screen.getByTestId("user-revision-notice").textContent).toContain("不能验证这些手工修改")
  expect(api.applyCodeEdit).not.toHaveBeenCalled()
})

it("does not query operation history for every typed character", async () => {
  render(view()); await openLoaded()
  await waitFor(() => expect(api.listCodeEdits).toHaveBeenCalledTimes(2))
  for (const value of ["a", "ab", "abc"]) fireEvent.change(screen.getByLabelText("完整源码"), { target: { value } })
  expect(api.listCodeEdits).toHaveBeenCalledTimes(2)
})

it("preserves uniform CRLF even though browser textareas expose LF values", async () => {
  vi.mocked(api.loadCodeEditSource).mockResolvedValue({ ...source, content: "one\r\ntwo\r\n" })
  render(view()); fireEvent.click(screen.getByText("编辑完整源码 / 应用补丁")); fireEvent.click(screen.getByText("读取完整源码"))
  const input = await screen.findByLabelText("完整源码")
  fireEvent.change(input, { target: { value: "one\nchanged\n" } })
  fireEvent.click(screen.getByText("检查并生成差异")); await screen.findByText("应用以上差异")
  expect(vi.mocked(api.prepareCodeEdit).mock.lastCall![2]).toHaveProperty("content", "one\r\nchanged\r\n")
})
