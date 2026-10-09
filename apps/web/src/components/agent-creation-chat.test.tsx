import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { AgentCreationChat } from "./agent-creation-chat"
import type { AgentCreationResult, TargetProject } from "@/lib/api"

const mocks = vi.hoisted(() => ({ generate: vi.fn(), save: vi.fn() }))
vi.mock("@/lib/api", async (original) => ({ ...await original<typeof import("@/lib/api")>(), generateAgentConfiguration: mocks.generate, saveCustomAgent: mocks.save }))
afterEach(() => { cleanup(); sessionStorage.clear(); vi.restoreAllMocks(); vi.clearAllMocks() })
const targets = [{ targetId: "demo-frontend", name: "演示前端", requiresPlatformMode: false, allowedAgents: ["frontend", "qa", "review"] }] as TargetProject[]
const props = { backendUrl: "http://api", workspaceId: "workspace", targets, onSaved: vi.fn().mockResolvedValue(undefined) }
const result: AgentCreationResult = {
  kind: "draft", reply: "已生成只读草稿，请检查后保存。",
  draft: { displayName: "评审助手", mentionAlias: "access-review", role: "review", providerId: "local-claude-code-cli", toolPolicy: "claude_read_only", supportedTargets: ["demo-frontend"], capabilityTags: ["code_review"], systemPrompt: "只读评审，用中文", description: "可访问性", avatarInitials: "AR", enabled: false },
  provenance: { providerId: "claude-cli-planner", plannerSource: "real_llm", durationMs: 10, inputSha256: "input-hash", outputSha256: "output-hash" },
}
function open() { fireEvent.click(screen.getByText("打开创建对话")) }
function describe(text = "创建一个只读前端评审助手") { fireEvent.change(screen.getByLabelText("描述你想创建的 Agent"), { target: { value: text } }); fireEvent.click(screen.getByText("生成配置草稿")) }

it("generates without saving, refines actual manual edits, and explicitly saves an enabled Agent", async () => {
  mocks.generate.mockResolvedValue(result); mocks.save.mockResolvedValue({ id: "saved-agent", mentionAlias: "access-review", status: "available" })
  render(<AgentCreationChat {...props} />); open(); describe()
  await screen.findByText("检查生成的 Agent 配置")
  expect(mocks.save).not.toHaveBeenCalled()
  expect(screen.getByLabelText("启用自定义 Agent")).toHaveProperty("checked", false)
  fireEvent.change(screen.getByLabelText("自定义名称"), { target: { value: "手工命名" } })
  fireEvent.change(screen.getByLabelText("补充或调整 Agent 要求"), { target: { value: "按严重程度排序，保留手工命名" } })
  fireEvent.click(screen.getByText("发送调整要求"))
  await waitFor(() => expect(mocks.generate).toHaveBeenCalledTimes(2))
  expect(mocks.generate.mock.calls[1][2]).toMatchObject({ currentDraft: { displayName: "手工命名" }, history: [{ role: "user" }, { role: "assistant" }] })
  fireEvent.click(screen.getByLabelText("启用自定义 Agent")); fireEvent.click(screen.getByText("保存自定义 Agent"))
  await screen.findByText(/已保存 @access-review/)
  expect(mocks.save).toHaveBeenCalledWith("http://api", "workspace", expect.objectContaining({ enabled: true, toolPolicy: "claude_read_only" }), undefined)
  expect(props.onSaved).toHaveBeenCalledOnce()
})

it("restores edited draft and conversation after remount without an automatic request", async () => {
  mocks.generate.mockResolvedValue(result)
  const first = render(<AgentCreationChat {...props} />); open(); describe()
  await screen.findByText("检查生成的 Agent 配置")
  fireEvent.change(screen.getByLabelText("自定义 System Prompt", { exact: false }), { target: { value: "手工保留的标记 RESTORE_42" } })
  first.unmount()
  render(<AgentCreationChat {...props} />); open()
  expect(screen.getByLabelText("自定义 System Prompt", { exact: false })).toHaveProperty("value", "手工保留的标记 RESTORE_42")
  expect(screen.getByText(result.reply)).toBeTruthy()
  expect(mocks.generate).toHaveBeenCalledOnce()
})

it("keeps edits and request text after generation failure or clarification", async () => {
  mocks.generate.mockResolvedValueOnce(result).mockRejectedValueOnce(new Error("Planner 连接失败"))
  render(<AgentCreationChat {...props} />); open(); describe()
  await screen.findByText("检查生成的 Agent 配置")
  fireEvent.change(screen.getByLabelText("自定义名称"), { target: { value: "保留此名称" } })
  fireEvent.change(screen.getByLabelText("补充或调整 Agent 要求"), { target: { value: "补充要求" } }); fireEvent.click(screen.getByText("发送调整要求"))
  await screen.findByRole("alert")
  expect(screen.getByLabelText("自定义名称")).toHaveProperty("value", "保留此名称")
  expect(screen.getByLabelText("补充或调整 Agent 要求")).toHaveProperty("value", "补充要求")
  mocks.generate.mockResolvedValue({ ...result, kind: "clarification", reply: "请说明目标", draft: null })
  fireEvent.click(screen.getByText("发送调整要求")); await screen.findByText("请说明目标")
  expect(screen.getByLabelText("自定义名称")).toHaveProperty("value", "保留此名称")
  expect(mocks.save).not.toHaveBeenCalled()
})

it("blocks duplicate sends and edits while pending, and ignores results from a different workspace", async () => {
  let complete!: (value: AgentCreationResult) => void
  mocks.generate.mockReturnValue(new Promise<AgentCreationResult>((resolve) => { complete = resolve }))
  const view = render(<AgentCreationChat {...props} />); open(); describe()
  fireEvent.click(screen.getByText("正在生成配置…"))
  expect(mocks.generate).toHaveBeenCalledOnce()
  expect(screen.getByLabelText("描述你想创建的 Agent")).toHaveProperty("disabled", true)
  view.rerender(<AgentCreationChat {...props} workspaceId="another-workspace" />)
  await act(async () => { complete(result) })
  expect(screen.queryByText("检查生成的 Agent 配置")).toBeNull()
  expect(screen.getByLabelText("描述你想创建的 Agent")).toHaveProperty("value", "")
  expect(sessionStorage.getItem("agenthub:agent-creation:v1:http://api:another-workspace")).toBeNull()
})

it("does not offer a second create after a successful save whose directory refresh failed", async () => {
  mocks.generate.mockResolvedValue(result); mocks.save.mockResolvedValue({ id: "saved-agent", mentionAlias: "access-review", status: "disabled" })
  const refresh = vi.fn().mockRejectedValue(new Error("offline"))
  render(<AgentCreationChat {...props} onSaved={refresh} />); open(); describe(); await screen.findByText("检查生成的 Agent 配置")
  fireEvent.click(screen.getByText("保存自定义 Agent")); await screen.findByRole("alert")
  expect(screen.getByText(/已保存 @access-review/)).toBeTruthy()
  expect(screen.queryByText("保存自定义 Agent")).toBeNull()
  expect(mocks.save).toHaveBeenCalledOnce()
})

it("explains unavailable storage, retains in-page edits and requires confirmation to reset", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked") })
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked") })
  render(<AgentCreationChat {...props} />); open()
  expect(screen.getByText(/本次编辑仅保留在当前页面/)).toBeTruthy()
  fireEvent.change(screen.getByLabelText("描述你想创建的 Agent"), { target: { value: "重要草稿" } })
  fireEvent.click(screen.getByText("开始新的创建对话")); fireEvent.click(screen.getByText("保留草稿"))
  expect(screen.getByLabelText("描述你想创建的 Agent")).toHaveProperty("value", "重要草稿")
  fireEvent.click(screen.getByText("开始新的创建对话")); fireEvent.click(screen.getByText("确认重新开始"))
  expect(screen.getByLabelText("描述你想创建的 Agent")).toHaveProperty("value", "")
})

it("ignores malformed stored config instead of rendering an invalid role", () => {
  sessionStorage.setItem("agenthub:agent-creation:v1:http://api:workspace", JSON.stringify({ version: 1, prompt: "", history: [], draft: { role: "host_admin" }, saved: null, provenance: null }))
  render(<AgentCreationChat {...props} />); open()
  expect(screen.getByText(/旧草稿格式无效/)).toBeTruthy()
  expect(screen.queryByText("检查生成的 Agent 配置")).toBeNull()
})
